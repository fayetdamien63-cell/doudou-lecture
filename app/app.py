"""Doudou Lecture — la bibliothèque de l'école maternelle.

Petite application Flask + SQLite pensée pour tourner sur un Raspberry Pi.
Lancement en développement :  python3 app/app.py
En production :               gunicorn -w 2 -b 127.0.0.1:8000 app.app:app
"""

import os
import secrets
from datetime import date, timedelta
from functools import wraps

from flask import (
    Flask, abort, flash, jsonify, redirect, render_template, request,
    send_from_directory, session, url_for,
)

try:  # exécution en package (gunicorn app.app:app) ou en script direct
    from . import db as store
    from . import metadata
except ImportError:  # pragma: no cover
    import db as store
    import metadata

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.environ.get("DOUDOU_DATA", os.path.join(BASE_DIR, "data"))

app = Flask(__name__)
app.config.update(
    DATABASE=os.path.join(DATA_DIR, "bibliotheque.db"),
    COVERS_DIR=os.path.join(DATA_DIR, "covers"),
    # Durée de prêt par défaut, modifiable dans le formulaire.
    LOAN_DAYS=int(os.environ.get("DOUDOU_LOAN_DAYS", "14")),
    PIN=os.environ.get("DOUDOU_PIN", "").strip(),
    JSON_AS_ASCII=False,
    MAX_CONTENT_LENGTH=4 * 1024 * 1024,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    PERMANENT_SESSION_LIFETIME=timedelta(days=30),
)

# La clé de session est persistée pour que les connexions survivent aux redémarrages.
_secret_file = os.path.join(DATA_DIR, "secret_key")
os.makedirs(DATA_DIR, exist_ok=True)
if not os.path.exists(_secret_file):
    with open(os.open(_secret_file, os.O_CREAT | os.O_WRONLY, 0o600), "w") as fh:
        fh.write(secrets.token_hex(32))
with open(_secret_file) as fh:
    app.secret_key = fh.read().strip()

store.init_db(app)
app.teardown_appcontext(store.close_db)


# --------------------------------------------------------------------------
# Code d'accès (facultatif mais recommandé derrière un tunnel public)
# --------------------------------------------------------------------------

def login_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if app.config["PIN"] and not session.get("ok"):
            if request.path.startswith("/api/"):
                return jsonify({"error": "Authentification requise"}), 401
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)

    return wrapper


@app.route("/connexion", methods=["GET", "POST"])
def login():
    if not app.config["PIN"]:
        return redirect(url_for("catalogue"))
    if request.method == "POST":
        given = (request.form.get("pin") or "").strip()
        if secrets.compare_digest(given, app.config["PIN"]):
            session.permanent = True
            session["ok"] = True
            target = request.form.get("next") or url_for("catalogue")
            return redirect(target if target.startswith("/") else url_for("catalogue"))
        flash("Code incorrect 🙈", "error")
    return render_template("login.html", next=request.args.get("next", ""))


@app.route("/deconnexion")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.context_processor
def inject_globals():
    return {
        "today": date.today().isoformat(),
        "default_due": (
            date.today() + timedelta(days=app.config["LOAN_DAYS"])
        ).isoformat(),
        "pin_enabled": bool(app.config["PIN"]),
        "tag_kinds": store.TAG_KINDS,
    }


# --------------------------------------------------------------------------
# Pages
# --------------------------------------------------------------------------

@app.route("/")
@login_required
def catalogue():
    query = request.args.get("q", "").strip()
    tag = request.args.get("tag", "").strip()
    status = request.args.get("statut", "").strip()
    sort = request.args.get("tri", "title")
    books = store.list_books(query=query, tag=tag or None, status=status or None, sort=sort)
    return render_template(
        "catalogue.html",
        books=books,
        query=query,
        tag=tag,
        status=status,
        sort=sort,
        tags=store.list_tags(only_used=True),
        stats=store.stats(),
    )


@app.route("/livre/<int:book_id>")
@login_required
def book_page(book_id):
    book = store.get_book(book_id)
    if not book:
        abort(404)
    return render_template("livre.html", book=book, tags=store.list_tags())


@app.route("/ajouter")
@login_required
def add_page():
    return render_template("ajouter.html", tags=store.list_tags())


@app.route("/emprunts")
@login_required
def loans_page():
    status = request.args.get("statut", "open")
    return render_template(
        "emprunts.html",
        loans=store.list_loans(status),
        status=status,
        stats=store.stats(),
    )


@app.route("/covers/<path:filename>")
@login_required
def cover(filename):
    return send_from_directory(app.config["COVERS_DIR"], filename, max_age=604800)


@app.errorhandler(404)
def not_found(_e):
    return render_template("404.html"), 404


# --------------------------------------------------------------------------
# API JSON
# --------------------------------------------------------------------------

@app.route("/api/lookup")
@login_required
def api_lookup():
    """Cherche un livre sur Internet à partir de l'ISBN lu au scanner."""
    raw = request.args.get("isbn", "")
    isbn = metadata.clean_isbn(raw)
    if not isbn:
        return jsonify({"error": "Code-barres invalide : %s" % raw}), 400
    existing = store.find_by_isbn(isbn)
    info = metadata.lookup(isbn)
    if not info:
        return jsonify({"error": "Livre introuvable en ligne", "isbn": isbn,
                        "existing_id": existing}), 404
    info["existing_id"] = existing
    return jsonify(info)


@app.route("/api/recherche-titre")
@login_required
def api_search_title():
    query = request.args.get("q", "").strip()
    if len(query) < 3:
        return jsonify({"results": []})
    return jsonify({"results": metadata.search_by_title(query)})


def _tags_from_payload(payload):
    tags = []
    for item in payload.get("tags") or []:
        if isinstance(item, str):
            tags.append({"name": item, "kind": "theme"})
        elif isinstance(item, dict):
            tags.append({"name": item.get("name", ""), "kind": item.get("kind", "theme")})
    return tags


def _handle_cover(payload, isbn, book_id):
    """Télécharge la couverture distante, sinon garde la valeur déjà en base."""
    cover_url = (payload.get("cover_url") or "").strip()
    if not cover_url:
        return (payload.get("cover") or "").strip()
    if cover_url.startswith("/covers/"):
        return cover_url.rsplit("/", 1)[-1]
    name = isbn or ("livre-%s" % (book_id or secrets.token_hex(4)))
    return metadata.download_cover(cover_url, app.config["COVERS_DIR"], name) or ""


@app.route("/api/livres", methods=["POST"])
@login_required
def api_create_book():
    payload = request.get_json(silent=True) or {}
    if not (payload.get("title") or "").strip():
        return jsonify({"error": "Le titre est obligatoire"}), 400
    isbn = metadata.clean_isbn(payload.get("isbn"))
    if isbn and store.find_by_isbn(isbn):
        return jsonify({"error": "Ce livre est déjà dans la bibliothèque",
                        "existing_id": store.find_by_isbn(isbn)}), 409
    data = dict(payload)
    data["isbn"] = isbn
    data["tags"] = _tags_from_payload(payload)
    data["cover"] = _handle_cover(payload, isbn, None)
    book_id = store.save_book(data)
    return jsonify({"id": book_id, "url": url_for("book_page", book_id=book_id)}), 201


@app.route("/api/livres/<int:book_id>", methods=["PUT"])
@login_required
def api_update_book(book_id):
    book = store.get_book(book_id)
    if not book:
        abort(404)
    payload = request.get_json(silent=True) or {}
    isbn = metadata.clean_isbn(payload.get("isbn"))
    other = store.find_by_isbn(isbn) if isbn else None
    if other and other != book_id:
        return jsonify({"error": "Un autre livre porte déjà cet ISBN"}), 409
    data = dict(payload)
    data["isbn"] = isbn
    data["tags"] = _tags_from_payload(payload)
    data["cover"] = _handle_cover(payload, isbn, book_id) or book["cover"]
    store.save_book(data, book_id=book_id)
    return jsonify({"id": book_id})


@app.route("/api/livres/<int:book_id>", methods=["DELETE"])
@login_required
def api_delete_book(book_id):
    if not store.get_book(book_id):
        abort(404)
    store.delete_book(book_id)
    return jsonify({"ok": True})


@app.route("/api/livres")
@login_required
def api_list_books():
    return jsonify(
        {
            "books": store.list_books(
                query=request.args.get("q", ""),
                tag=request.args.get("tag") or None,
                status=request.args.get("statut") or None,
                sort=request.args.get("tri", "title"),
            )
        }
    )


@app.route("/api/tags")
@login_required
def api_tags():
    return jsonify({"tags": store.list_tags()})


@app.route("/api/eleves")
@login_required
def api_students():
    return jsonify({"students": store.list_students()})


@app.route("/api/emprunts", methods=["POST"])
@login_required
def api_create_loan():
    payload = request.get_json(silent=True) or {}
    student = (payload.get("student") or "").strip()
    book_id = payload.get("book_id")
    if not student:
        return jsonify({"error": "Le prénom de l'élève est obligatoire"}), 400
    if not store.get_book(book_id):
        return jsonify({"error": "Livre inconnu"}), 404
    loaned_on = (payload.get("loaned_on") or date.today().isoformat())[:10]
    due_on = (payload.get("due_on") or "")[:10] or None
    try:
        loan_id = store.create_loan(
            book_id, student, payload.get("classroom", ""), loaned_on, due_on
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 409
    return jsonify({"id": loan_id}), 201


@app.route("/api/emprunts/<int:loan_id>/retour", methods=["POST"])
@login_required
def api_return_loan(loan_id):
    payload = request.get_json(silent=True) or {}
    store.return_loan(loan_id, (payload.get("returned_on") or date.today().isoformat())[:10])
    return jsonify({"ok": True})


@app.route("/api/stats")
@login_required
def api_stats():
    return jsonify(store.stats())


if __name__ == "__main__":  # pragma: no cover
    app.run(
        host=os.environ.get("DOUDOU_HOST", "0.0.0.0"),
        port=int(os.environ.get("DOUDOU_PORT", "8000")),
        debug=bool(os.environ.get("DOUDOU_DEBUG")),
    )
