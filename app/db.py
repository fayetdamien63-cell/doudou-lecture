"""Accès SQLite (bibliothèque de l'école maternelle).

Volontairement sans ORM : sqlite3 de la bibliothèque standard uniquement,
pour rester très léger sur un Raspberry Pi 1B+.
"""

import os
import sqlite3
import unicodedata
from datetime import date

from flask import current_app, g

SCHEMA = """
CREATE TABLE IF NOT EXISTS books (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    isbn           TEXT UNIQUE,
    title          TEXT NOT NULL,
    authors        TEXT DEFAULT '',
    publisher      TEXT DEFAULT '',
    year           TEXT DEFAULT '',
    summary        TEXT DEFAULT '',
    page_count     INTEGER,
    age_min        INTEGER,
    age_max        INTEGER,
    location       TEXT DEFAULT '',
    cover          TEXT DEFAULT '',
    search_blob    TEXT DEFAULT '',
    created_at     TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS tags (
    id    INTEGER PRIMARY KEY AUTOINCREMENT,
    name  TEXT NOT NULL,
    kind  TEXT NOT NULL DEFAULT 'theme',
    UNIQUE (name, kind)
);

CREATE TABLE IF NOT EXISTS book_tags (
    book_id INTEGER NOT NULL REFERENCES books(id) ON DELETE CASCADE,
    tag_id  INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    PRIMARY KEY (book_id, tag_id)
);

CREATE TABLE IF NOT EXISTS loans (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    book_id      INTEGER NOT NULL REFERENCES books(id) ON DELETE CASCADE,
    student      TEXT NOT NULL,
    classroom    TEXT DEFAULT '',
    loaned_on    TEXT NOT NULL,
    due_on       TEXT,
    returned_on  TEXT
);

CREATE INDEX IF NOT EXISTS idx_books_search ON books(search_blob);
CREATE INDEX IF NOT EXISTS idx_loans_book   ON loans(book_id);
CREATE INDEX IF NOT EXISTS idx_loans_open   ON loans(returned_on);
"""

# Quelques thèmes proposés d'office dans l'interface.
DEFAULT_TAGS = [
    ("Animaux", "theme"), ("Amitié", "theme"), ("École", "theme"),
    ("Famille", "theme"), ("Émotions", "theme"), ("Saisons", "theme"),
    ("Noël", "theme"), ("Nuit / Dodo", "theme"), ("Contes", "theme"),
    ("Imagier", "theme"), ("Comptines", "theme"), ("Nature", "theme"),
    ("Corps humain", "theme"), ("Nourriture", "theme"), ("Voyage", "theme"),
    ("Loup", "personnage"), ("Sorcière", "personnage"), ("Princesse", "personnage"),
    ("Pirate", "personnage"), ("Dragon", "personnage"), ("Monstre", "personnage"),
    ("Ours", "animal"), ("Lapin", "animal"), ("Souris", "animal"),
    ("Chat", "animal"), ("Chien", "animal"), ("Éléphant", "animal"),
    ("Poisson", "animal"), ("Oiseau", "animal"), ("Escargot", "animal"),
]

TAG_KINDS = ("theme", "personnage", "animal", "autre")


def normalize(text):
    """Minuscules sans accents : permet de chercher « elephant » et trouver « éléphant »."""
    if not text:
        return ""
    text = unicodedata.normalize("NFD", str(text))
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    return " ".join(text.lower().split())


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(
            current_app.config["DATABASE"],
            detect_types=sqlite3.PARSE_DECLTYPES,
            timeout=15,
        )
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
        try:
            # WAL accélère les lectures pendant une écriture, mais n'est pas
            # disponible sur certains systèmes de fichiers réseau (PythonAnywhere).
            g.db.execute("PRAGMA journal_mode = WAL")
        except sqlite3.DatabaseError:
            pass
    return g.db


def close_db(_exc=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db(app):
    os.makedirs(os.path.dirname(app.config["DATABASE"]), exist_ok=True)
    os.makedirs(app.config["COVERS_DIR"], exist_ok=True)
    db = sqlite3.connect(app.config["DATABASE"])
    db.executescript(SCHEMA)
    db.executemany(
        "INSERT OR IGNORE INTO tags (name, kind) VALUES (?, ?)", DEFAULT_TAGS
    )
    db.commit()
    db.close()


# --------------------------------------------------------------------------
# Livres
# --------------------------------------------------------------------------

def build_search_blob(book, tag_names):
    parts = [
        book.get("title", ""), book.get("authors", ""), book.get("publisher", ""),
        book.get("summary", ""), book.get("isbn", ""), book.get("location", ""),
    ] + list(tag_names)
    return normalize(" ".join(p for p in parts if p))


def _tag_ids(db, tags):
    """`tags` : liste de dicts {name, kind}. Crée les tags manquants."""
    ids = []
    for tag in tags:
        name = (tag.get("name") or "").strip()
        if not name:
            continue
        kind = tag.get("kind") if tag.get("kind") in TAG_KINDS else "theme"
        db.execute("INSERT OR IGNORE INTO tags (name, kind) VALUES (?, ?)", (name, kind))
        row = db.execute(
            "SELECT id FROM tags WHERE name = ? AND kind = ?", (name, kind)
        ).fetchone()
        if row:
            ids.append(row["id"])
    return ids


def save_book(data, book_id=None):
    """Crée ou met à jour un livre. Renvoie l'id."""
    db = get_db()
    tags = data.get("tags") or []
    tag_names = [t.get("name", "") for t in tags]
    fields = {
        "isbn": (data.get("isbn") or "").strip() or None,
        "title": (data.get("title") or "").strip() or "Sans titre",
        "authors": (data.get("authors") or "").strip(),
        "publisher": (data.get("publisher") or "").strip(),
        "year": str(data.get("year") or "").strip(),
        "summary": (data.get("summary") or "").strip(),
        "page_count": data.get("page_count") or None,
        "age_min": data.get("age_min") or None,
        "age_max": data.get("age_max") or None,
        "location": (data.get("location") or "").strip(),
        "cover": (data.get("cover") or "").strip(),
    }
    fields["search_blob"] = build_search_blob(fields, tag_names)

    if book_id:
        db.execute(
            """UPDATE books SET isbn=:isbn, title=:title, authors=:authors,
                   publisher=:publisher, year=:year, summary=:summary,
                   page_count=:page_count, age_min=:age_min, age_max=:age_max,
                   location=:location, cover=:cover, search_blob=:search_blob
               WHERE id=:id""",
            dict(fields, id=book_id),
        )
    else:
        cur = db.execute(
            """INSERT INTO books (isbn, title, authors, publisher, year, summary,
                                  page_count, age_min, age_max, location, cover, search_blob)
               VALUES (:isbn, :title, :authors, :publisher, :year, :summary,
                       :page_count, :age_min, :age_max, :location, :cover, :search_blob)""",
            fields,
        )
        book_id = cur.lastrowid

    db.execute("DELETE FROM book_tags WHERE book_id = ?", (book_id,))
    for tag_id in _tag_ids(db, tags):
        db.execute(
            "INSERT OR IGNORE INTO book_tags (book_id, tag_id) VALUES (?, ?)",
            (book_id, tag_id),
        )
    db.commit()
    return book_id


def delete_book(book_id):
    db = get_db()
    db.execute("DELETE FROM books WHERE id = ?", (book_id,))
    db.commit()


def _row_to_book(row):
    book = dict(row)
    book["tags"] = []
    loan = None
    if book.pop("loan_id", None):
        loan = {
            "id": row["loan_id"],
            "student": row["loan_student"],
            "classroom": row["loan_classroom"],
            "loaned_on": row["loaned_on"],
            "due_on": row["due_on"],
            "late": bool(row["due_on"] and row["due_on"] < date.today().isoformat()),
        }
    for key in ("loan_student", "loan_classroom", "loaned_on", "due_on"):
        book.pop(key, None)
    book["loan"] = loan
    book["available"] = loan is None
    return book


BOOK_SELECT = """
SELECT b.*,
       l.id        AS loan_id,
       l.student   AS loan_student,
       l.classroom AS loan_classroom,
       l.loaned_on AS loaned_on,
       l.due_on    AS due_on
  FROM books b
  LEFT JOIN loans l ON l.book_id = b.id AND l.returned_on IS NULL
"""


def list_books(query="", tag=None, status=None, sort="title", limit=500, offset=0):
    db = get_db()
    sql = BOOK_SELECT
    params = []
    where = []

    if tag:
        sql += """ JOIN book_tags bt ON bt.book_id = b.id
                   JOIN tags t ON t.id = bt.tag_id AND t.name = ?"""
        params.append(tag)

    if query:
        for word in normalize(query).split():
            where.append("b.search_blob LIKE ?")
            params.append("%" + word + "%")

    if status == "available":
        where.append("l.id IS NULL")
    elif status == "loaned":
        where.append("l.id IS NOT NULL")
    elif status == "late":
        where.append("l.id IS NOT NULL AND l.due_on IS NOT NULL AND l.due_on < ?")
        params.append(date.today().isoformat())

    if where:
        sql += " WHERE " + " AND ".join(where)

    orders = {
        "title": "b.title COLLATE NOCASE ASC",
        "recent": "b.id DESC",
        "author": "b.authors COLLATE NOCASE ASC, b.title COLLATE NOCASE ASC",
    }
    sql += " ORDER BY " + orders.get(sort, orders["title"])
    sql += " LIMIT ? OFFSET ?"
    params += [limit, offset]

    books = [_row_to_book(r) for r in db.execute(sql, params)]
    _attach_tags(db, books)
    return books


def _attach_tags(db, books):
    if not books:
        return
    by_id = {b["id"]: b for b in books}
    placeholders = ",".join("?" * len(by_id))
    rows = db.execute(
        f"""SELECT bt.book_id, t.name, t.kind FROM book_tags bt
            JOIN tags t ON t.id = bt.tag_id
            WHERE bt.book_id IN ({placeholders})
            ORDER BY t.kind, t.name COLLATE NOCASE""",
        list(by_id),
    )
    for row in rows:
        by_id[row["book_id"]]["tags"].append({"name": row["name"], "kind": row["kind"]})


def get_book(book_id):
    db = get_db()
    row = db.execute(BOOK_SELECT + " WHERE b.id = ?", (book_id,)).fetchone()
    if not row:
        return None
    book = _row_to_book(row)
    _attach_tags(db, [book])
    book["history"] = [
        dict(r)
        for r in db.execute(
            """SELECT id, student, classroom, loaned_on, due_on, returned_on
                 FROM loans WHERE book_id = ?
             ORDER BY loaned_on DESC, id DESC LIMIT 30""",
            (book_id,),
        )
    ]
    return book


def find_by_isbn(isbn):
    db = get_db()
    row = db.execute("SELECT id FROM books WHERE isbn = ?", (isbn,)).fetchone()
    return row["id"] if row else None


# --------------------------------------------------------------------------
# Tags
# --------------------------------------------------------------------------

def list_tags(only_used=False):
    db = get_db()
    sql = """SELECT t.id, t.name, t.kind, COUNT(bt.book_id) AS count
               FROM tags t LEFT JOIN book_tags bt ON bt.tag_id = t.id
           GROUP BY t.id ORDER BY t.kind, t.name COLLATE NOCASE"""
    tags = [dict(r) for r in db.execute(sql)]
    if only_used:
        tags = [t for t in tags if t["count"] > 0]
    return tags


def delete_unused_tag(tag_id):
    db = get_db()
    db.execute(
        "DELETE FROM tags WHERE id = ? AND id NOT IN (SELECT tag_id FROM book_tags)",
        (tag_id,),
    )
    db.commit()


# --------------------------------------------------------------------------
# Emprunts
# --------------------------------------------------------------------------

def create_loan(book_id, student, classroom, loaned_on, due_on):
    db = get_db()
    open_loan = db.execute(
        "SELECT id FROM loans WHERE book_id = ? AND returned_on IS NULL", (book_id,)
    ).fetchone()
    if open_loan:
        raise ValueError("Ce livre est déjà emprunté.")
    cur = db.execute(
        """INSERT INTO loans (book_id, student, classroom, loaned_on, due_on)
           VALUES (?, ?, ?, ?, ?)""",
        (book_id, student.strip(), (classroom or "").strip(), loaned_on, due_on or None),
    )
    db.commit()
    return cur.lastrowid


def return_loan(loan_id, returned_on):
    db = get_db()
    db.execute(
        "UPDATE loans SET returned_on = ? WHERE id = ? AND returned_on IS NULL",
        (returned_on, loan_id),
    )
    db.commit()


def list_loans(status="open"):
    db = get_db()
    sql = """SELECT l.*, b.title, b.cover, b.authors
               FROM loans l JOIN books b ON b.id = l.book_id"""
    if status == "open":
        sql += " WHERE l.returned_on IS NULL ORDER BY l.due_on IS NULL, l.due_on ASC"
    elif status == "closed":
        sql += " WHERE l.returned_on IS NOT NULL ORDER BY l.returned_on DESC LIMIT 200"
    else:
        sql += " ORDER BY l.loaned_on DESC LIMIT 300"
    today = date.today().isoformat()
    loans = []
    for row in db.execute(sql):
        loan = dict(row)
        loan["late"] = bool(
            not loan["returned_on"] and loan["due_on"] and loan["due_on"] < today
        )
        loans.append(loan)
    return loans


def list_students():
    db = get_db()
    return [
        r["student"]
        for r in db.execute(
            "SELECT student, COUNT(*) c FROM loans GROUP BY student COLLATE NOCASE"
            " ORDER BY c DESC, student COLLATE NOCASE LIMIT 200"
        )
    ]


def stats():
    db = get_db()
    today = date.today().isoformat()
    one = lambda sql, *p: db.execute(sql, p).fetchone()[0]  # noqa: E731
    return {
        "books": one("SELECT COUNT(*) FROM books"),
        "loaned": one("SELECT COUNT(*) FROM loans WHERE returned_on IS NULL"),
        "late": one(
            "SELECT COUNT(*) FROM loans WHERE returned_on IS NULL"
            " AND due_on IS NOT NULL AND due_on < ?",
            today,
        ),
        "tags": one("SELECT COUNT(*) FROM tags WHERE id IN (SELECT tag_id FROM book_tags)"),
    }
