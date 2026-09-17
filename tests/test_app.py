"""Tests de bout en bout (aucun accès réseau : les recherches sont simulées).

Lancement :  python3 -m unittest discover -s tests
"""

import os
import shutil
import sys
import tempfile
import unittest
from datetime import date, timedelta

TMP = tempfile.mkdtemp(prefix="doudou-test-")
os.environ["DOUDOU_DATA"] = TMP
os.environ["DOUDOU_PIN"] = ""

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app as module  # noqa: E402
from app import db as store  # noqa: E402
from app import metadata  # noqa: E402


def tearDownModule():
    shutil.rmtree(TMP, ignore_errors=True)


class BaseCase(unittest.TestCase):
    def setUp(self):
        module.app.config["TESTING"] = True
        self.client = module.app.test_client()
        with module.app.app_context():
            db = store.get_db()
            db.executescript(
                "DELETE FROM loans; DELETE FROM book_tags; DELETE FROM books;"
            )
            db.commit()

    def add_book(self, **overrides):
        payload = {
            "title": "Le loup qui voulait changer de couleur",
            "authors": "Orianne Lallemand",
            "isbn": "9782211013512",
            "tags": [{"name": "Loup", "kind": "personnage"}, {"name": "Émotions", "kind": "theme"}],
        }
        payload.update(overrides)
        response = self.client.post("/api/livres", json=payload)
        self.assertEqual(response.status_code, 201, response.get_data(as_text=True))
        return response.get_json()["id"]


class IsbnTests(unittest.TestCase):
    def test_clean_isbn(self):
        self.assertEqual(metadata.clean_isbn("978-2-211-01351-2"), "9782211013512")
        self.assertEqual(metadata.clean_isbn("2211013511"), "9782211013512")  # ISBN-10
        self.assertEqual(metadata.clean_isbn("9782211013519"), "")  # mauvaise clé
        self.assertEqual(metadata.clean_isbn("bonjour"), "")
        self.assertEqual(metadata.clean_isbn(None), "")


class NormalizeTests(unittest.TestCase):
    def test_accents_are_ignored(self):
        self.assertEqual(store.normalize("Éléphant   ROSE"), "elephant rose")


class BookTests(BaseCase):
    def test_create_and_read(self):
        book_id = self.add_book()
        page = self.client.get("/livre/%d" % book_id)
        self.assertEqual(page.status_code, 200)
        self.assertIn("Orianne Lallemand", page.get_data(as_text=True))

    def test_title_is_required(self):
        response = self.client.post("/api/livres", json={"title": "  "})
        self.assertEqual(response.status_code, 400)

    def test_duplicate_isbn_is_refused(self):
        first = self.add_book()
        response = self.client.post(
            "/api/livres", json={"title": "Doublon", "isbn": "9782211013512"}
        )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.get_json()["existing_id"], first)

    def test_search_ignores_accents_and_case(self):
        self.add_book(title="L'éléphant rose", isbn="", tags=[])
        for query in ("elephant", "ÉLÉPHANT", "rose elephant"):
            books = self.client.get("/api/livres?q=" + query).get_json()["books"]
            self.assertEqual(len(books), 1, query)

    def test_search_by_tag_and_person(self):
        self.add_book()
        books = self.client.get("/api/livres?tag=Loup").get_json()["books"]
        self.assertEqual(len(books), 1)
        self.assertEqual(
            self.client.get("/api/livres?tag=Chat").get_json()["books"], []
        )
        # Le contenu des étiquettes est aussi indexé dans la recherche libre.
        self.assertEqual(len(self.client.get("/api/livres?q=loup").get_json()["books"]), 1)

    def test_update_and_delete(self):
        book_id = self.add_book()
        response = self.client.put(
            "/api/livres/%d" % book_id,
            json={"title": "Nouveau titre", "isbn": "9782211013512", "tags": []},
        )
        self.assertEqual(response.status_code, 200)
        page = self.client.get("/livre/%d" % book_id).get_data(as_text=True)
        self.assertIn("Nouveau titre", page)

        self.assertEqual(self.client.delete("/api/livres/%d" % book_id).status_code, 200)
        self.assertEqual(self.client.get("/livre/%d" % book_id).status_code, 404)


class LoanTests(BaseCase):
    def test_loan_then_return(self):
        book_id = self.add_book()
        due = (date.today() + timedelta(days=14)).isoformat()
        created = self.client.post(
            "/api/emprunts",
            json={"book_id": book_id, "student": "Camille", "classroom": "GS", "due_on": due},
        )
        self.assertEqual(created.status_code, 201)
        loan_id = created.get_json()["id"]

        books = self.client.get("/api/livres?statut=loaned").get_json()["books"]
        self.assertEqual(books[0]["loan"]["student"], "Camille")
        self.assertFalse(books[0]["available"])
        self.assertEqual(self.client.get("/api/livres?statut=available").get_json()["books"], [])

        # Un livre déjà emprunté ne peut pas être prêté deux fois.
        again = self.client.post(
            "/api/emprunts", json={"book_id": book_id, "student": "Noé"}
        )
        self.assertEqual(again.status_code, 409)

        self.assertEqual(
            self.client.post("/api/emprunts/%d/retour" % loan_id, json={}).status_code, 200
        )
        self.assertTrue(
            self.client.get("/api/livres?statut=available").get_json()["books"][0]["available"]
        )

    def test_student_is_required(self):
        book_id = self.add_book()
        response = self.client.post("/api/emprunts", json={"book_id": book_id, "student": " "})
        self.assertEqual(response.status_code, 400)

    def test_late_loans_are_flagged(self):
        book_id = self.add_book()
        late_due = (date.today() - timedelta(days=3)).isoformat()
        self.client.post(
            "/api/emprunts",
            json={"book_id": book_id, "student": "Lou", "due_on": late_due},
        )
        books = self.client.get("/api/livres?statut=late").get_json()["books"]
        self.assertEqual(len(books), 1)
        self.assertTrue(books[0]["loan"]["late"])
        self.assertEqual(self.client.get("/api/stats").get_json()["late"], 1)


class LookupTests(BaseCase):
    def test_invalid_barcode(self):
        response = self.client.get("/api/lookup?isbn=42")
        self.assertEqual(response.status_code, 400)

    def test_lookup_uses_metadata_module(self):
        fake = {
            "isbn": "9782211013512", "title": "Loulou", "authors": "Grégoire Solotareff",
            "publisher": "L'école des loisirs", "year": "1989", "summary": "",
            "page_count": 36, "categories": ["Juvenile Fiction"], "cover_url": "",
            "source": "Test",
        }
        original = module.metadata.lookup
        module.metadata.lookup = lambda isbn: fake
        try:
            data = self.client.get("/api/lookup?isbn=9782211013512").get_json()
        finally:
            module.metadata.lookup = original
        self.assertEqual(data["title"], "Loulou")
        self.assertIsNone(data["existing_id"])


class PageTests(BaseCase):
    def test_pages_render(self):
        self.add_book()
        for url in ("/", "/ajouter", "/emprunts", "/api/stats", "/api/tags"):
            self.assertEqual(self.client.get(url).status_code, 200, url)

    def test_unknown_page(self):
        self.assertEqual(self.client.get("/livre/9999").status_code, 404)


if __name__ == "__main__":
    unittest.main()
