"""Recherche des informations d'un livre à partir de son ISBN / code-barres.

Sources utilisées, toutes libres et sans clé d'API :
  1. Google Books   (https://www.googleapis.com/books/v1/volumes)
  2. Open Library   (https://openlibrary.org/api/books)
  3. Couverture Open Library (https://covers.openlibrary.org)

Uniquement la bibliothèque standard : pas de dépendance supplémentaire à
installer sur le Raspberry Pi.
"""

import json
import os
import re
import socket
import urllib.error
import urllib.parse
import urllib.request

TIMEOUT = 8
USER_AGENT = "Doudou-Lecture/1.0 (bibliotheque ecole maternelle)"


# --------------------------------------------------------------------------
# ISBN
# --------------------------------------------------------------------------

def clean_isbn(raw):
    """Nettoie un ISBN / EAN-13 lu au scanner. Renvoie '' si invalide."""
    if not raw:
        return ""
    value = re.sub(r"[^0-9Xx]", "", str(raw)).upper()
    if len(value) == 10 and _isbn10_ok(value):
        return _isbn10_to_13(value)
    if len(value) == 13 and value.startswith(("978", "979")) and _ean13_ok(value):
        return value
    return ""


def _isbn10_ok(value):
    total = 0
    for i, char in enumerate(value):
        digit = 10 if char == "X" else (int(char) if char.isdigit() else -1)
        if digit < 0:
            return False
        total += (10 - i) * digit
    return total % 11 == 0


def _ean13_ok(value):
    if not value.isdigit():
        return False
    total = sum(int(c) * (1 if i % 2 == 0 else 3) for i, c in enumerate(value[:12]))
    return (10 - total % 10) % 10 == int(value[12])


def _isbn10_to_13(value):
    core = "978" + value[:9]
    total = sum(int(c) * (1 if i % 2 == 0 else 3) for i, c in enumerate(core))
    return core + str((10 - total % 10) % 10)


# --------------------------------------------------------------------------
# Requêtes HTTP
# --------------------------------------------------------------------------

def _get_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return json.loads(resp.read().decode("utf-8", "replace"))
    except (urllib.error.URLError, socket.timeout, ValueError, OSError):
        return None


def _from_google(isbn):
    data = _get_json(
        "https://www.googleapis.com/books/v1/volumes?country=FR&q="
        + urllib.parse.quote("isbn:" + isbn)
    )
    if not data or not data.get("items"):
        return None
    info = data["items"][0].get("volumeInfo", {})
    images = info.get("imageLinks", {}) or {}
    cover = (
        images.get("thumbnail")
        or images.get("smallThumbnail")
        or ""
    ).replace("http://", "https://").replace("&edge=curl", "")
    return {
        "isbn": isbn,
        "title": info.get("title", ""),
        "subtitle": info.get("subtitle", ""),
        "authors": ", ".join(info.get("authors", []) or []),
        "publisher": info.get("publisher", ""),
        "year": (info.get("publishedDate") or "")[:4],
        "summary": info.get("description", "") or "",
        "page_count": info.get("pageCount") or None,
        "categories": info.get("categories", []) or [],
        "cover_url": cover,
        "source": "Google Books",
    }


def _ol_text(value):
    """Open Library renvoie soit une chaîne, soit {"value": "..."}."""
    if isinstance(value, dict):
        return value.get("value", "")
    return value if isinstance(value, str) else ""


def _from_openlibrary(isbn):
    """Open Library : /isbn/<isbn>.json, complété par l'œuvre et les auteurs."""
    edition = _get_json("https://openlibrary.org/isbn/%s.json" % isbn)
    if not edition or not edition.get("title"):
        return None

    authors = []
    for author in (edition.get("authors") or [])[:3]:
        key = author.get("key")
        if not key:
            continue
        detail = _get_json("https://openlibrary.org%s.json" % key)
        if detail and detail.get("name"):
            authors.append(detail["name"])

    summary, categories = "", []
    works = edition.get("works") or []
    if works and works[0].get("key"):
        work = _get_json("https://openlibrary.org%s.json" % works[0]["key"])
        if work:
            summary = _ol_text(work.get("description"))
            categories = [s for s in (work.get("subjects") or []) if isinstance(s, str)][:12]

    covers = [c for c in (edition.get("covers") or []) if isinstance(c, int) and c > 0]
    cover_url = (
        "https://covers.openlibrary.org/b/id/%d-L.jpg" % covers[0] if covers else ""
    )

    return {
        "isbn": isbn,
        "title": edition.get("title", ""),
        "subtitle": edition.get("subtitle", ""),
        "authors": ", ".join(authors),
        "publisher": ", ".join(
            p for p in (edition.get("publishers") or []) if isinstance(p, str)
        ),
        "year": (edition.get("publish_date") or "")[-4:],
        "summary": summary,
        "page_count": edition.get("number_of_pages") or None,
        "categories": categories,
        "cover_url": cover_url,
        "source": "Open Library",
    }


def lookup(isbn):
    """Interroge les sources l'une après l'autre et fusionne les champs manquants."""
    isbn = clean_isbn(isbn)
    if not isbn:
        return None

    result = None
    for fetch in (_from_google, _from_openlibrary):
        data = fetch(isbn)
        if not data or not data.get("title"):
            continue
        if result is None:
            result = data
        else:
            for field, value in data.items():
                if value and not result.get(field):
                    result[field] = value
            result["source"] += " + " + data["source"]

    if result is None:
        return None

    if not result.get("cover_url"):
        result["cover_url"] = (
            "https://covers.openlibrary.org/b/isbn/%s-L.jpg?default=false" % isbn
        )
    if result.get("subtitle") and result["subtitle"] not in result["title"]:
        result["title"] = "%s – %s" % (result["title"], result["subtitle"])
    return result


def search_by_title(query, limit=10):
    """Recherche par titre quand le code-barres ne donne rien."""
    data = _get_json(
        "https://www.googleapis.com/books/v1/volumes?country=FR&maxResults=%d&q=%s"
        % (limit, urllib.parse.quote(query))
    )
    results = []
    for item in (data or {}).get("items", []) or []:
        info = item.get("volumeInfo", {})
        isbns = {
            i.get("type"): i.get("identifier")
            for i in info.get("industryIdentifiers", []) or []
        }
        images = info.get("imageLinks", {}) or {}
        results.append(
            {
                "isbn": clean_isbn(isbns.get("ISBN_13") or isbns.get("ISBN_10") or ""),
                "title": info.get("title", ""),
                "authors": ", ".join(info.get("authors", []) or []),
                "publisher": info.get("publisher", ""),
                "year": (info.get("publishedDate") or "")[:4],
                "summary": info.get("description", "") or "",
                "page_count": info.get("pageCount") or None,
                "categories": info.get("categories", []) or [],
                "cover_url": (images.get("thumbnail") or "").replace("http://", "https://"),
                "source": "Google Books",
            }
        )
    return [r for r in results if r["title"]]


# --------------------------------------------------------------------------
# Couvertures : on les télécharge une fois pour toutes en local.
# --------------------------------------------------------------------------

MAX_COVER_BYTES = 2 * 1024 * 1024
EXTENSIONS = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp",
              "image/gif": ".gif"}


def download_cover(url, covers_dir, name):
    """Télécharge une couverture dans `covers_dir`. Renvoie le nom de fichier ou ''."""
    if not url or not url.startswith("https://"):
        return ""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            content_type = (resp.headers.get("Content-Type") or "").split(";")[0].strip()
            if content_type not in EXTENSIONS:
                return ""
            payload = resp.read(MAX_COVER_BYTES + 1)
    except (urllib.error.URLError, socket.timeout, OSError):
        return ""
    if not payload or len(payload) > MAX_COVER_BYTES or len(payload) < 512:
        return ""  # 1x1 px « pas de couverture » d'Open Library

    safe = re.sub(r"[^A-Za-z0-9_-]", "", str(name)) or "cover"
    filename = safe + EXTENSIONS[content_type]
    os.makedirs(covers_dir, exist_ok=True)
    with open(os.path.join(covers_dir, filename), "wb") as handle:
        handle.write(payload)
    return filename
