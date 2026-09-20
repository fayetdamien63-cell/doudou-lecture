"""Test de non-régression du formulaire d'ajout, dans un vrai navigateur.

Il vérifie qu'un deuxième scan ne laisse jamais la fiche du livre précédent
dans le formulaire — sans quoi le même livre serait enregistré plusieurs fois.

Ce test a besoin de Playwright et d'un navigateur ; il est automatiquement
ignoré s'ils ne sont pas installés (inutile de les mettre sur le Raspberry Pi) :

    pip install playwright && playwright install chromium
    python3 -m unittest tests.test_scan_navigateur
"""

import json
import os
import threading
import unittest
from wsgiref.simple_server import make_server

from tests import contexte  # noqa: F401  (prépare DOUDOU_DATA avant l'import)

try:
    from playwright.sync_api import sync_playwright
except ImportError:  # pragma: no cover
    sync_playwright = None

LOUP = {
    "isbn": "9782211013512", "title": "Le loup qui voulait changer de couleur",
    "authors": "Orianne Lallemand", "publisher": "Auzou", "year": "2009",
    "summary": "Un loup qui n'aime pas sa couleur.", "page_count": 32,
    "categories": [], "cover_url": "", "source": "Test", "existing_id": None,
}
PRINCE = {
    "isbn": "9782070601271", "title": "Le Petit Prince", "authors": "",
    "publisher": "", "year": "", "summary": "", "page_count": None,
    "categories": [], "cover_url": "", "source": "Test", "existing_id": None,
}
INTROUVABLE = {"error": "Livre introuvable en ligne", "isbn": "9782226392121",
               "existing_id": None}


@unittest.skipIf(sync_playwright is None, "Playwright n'est pas installé")
class FormulaireAjoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from app.app import app

        cls.server = make_server("127.0.0.1", 0, app)
        cls.url = "http://127.0.0.1:%d" % cls.server.server_port
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.playwright = sync_playwright().start()
        navigateur = "/opt/pw-browsers/chromium"
        cls.browser = cls.playwright.chromium.launch(
            executable_path=navigateur if os.path.exists(navigateur) else None
        )

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()
        cls.server.shutdown()

    def _page(self, reponses):
        """Ouvre /ajouter avec des réponses simulées pour /api/lookup."""
        page = self.browser.new_page(viewport={"width": 390, "height": 844})
        compteur = {"n": 0}

        def repondre(route):
            compteur["n"] += 1
            statut, corps = reponses[min(compteur["n"], len(reponses)) - 1]
            route.fulfill(status=statut, content_type="application/json",
                          body=json.dumps(corps))

        page.route("**/api/lookup**", repondre)
        page.goto(self.url + "/ajouter", wait_until="networkidle")
        return page

    def _chercher(self, page, isbn):
        page.fill("#isbn", isbn)
        page.click("#btn-lookup")
        page.wait_for_timeout(400)

    def test_livre_introuvable_ne_garde_pas_le_precedent(self):
        page = self._page([(200, LOUP), (404, INTROUVABLE)])
        page.fill("#f-location", "Bac bleu")
        self._chercher(page, LOUP["isbn"])
        self.assertEqual(page.input_value("#f-title"), LOUP["title"])

        self._chercher(page, "9782226392121")
        self.assertEqual(page.input_value("#f-title"), "")
        self.assertEqual(page.input_value("#f-authors"), "")
        self.assertEqual(page.input_value("#isbn"), "9782226392121")
        # Le rangement, lui, sert à toute une pile de livres.
        self.assertEqual(page.input_value("#f-location"), "Bac bleu")
        page.close()

    def test_fiche_incomplete_ne_melange_pas_deux_livres(self):
        page = self._page([(200, LOUP), (200, PRINCE)])
        self._chercher(page, LOUP["isbn"])
        self._chercher(page, PRINCE["isbn"])
        self.assertEqual(page.input_value("#f-title"), PRINCE["title"])
        for champ in ("#f-authors", "#f-publisher", "#f-summary", "#f-pages"):
            self.assertEqual(page.input_value(champ), "", champ)
        page.close()

    def test_formulaire_vide_apres_enregistrement(self):
        page = self._page([(200, LOUP)])
        page.fill("#f-location", "Bac vert")
        self._chercher(page, LOUP["isbn"])
        page.click("#btn-save")
        page.wait_for_timeout(800)
        self.assertEqual(page.input_value("#f-title"), "")
        self.assertEqual(page.input_value("#isbn"), "")
        self.assertEqual(page.input_value("#f-location"), "Bac vert")

        page.click("#btn-reset")
        page.wait_for_timeout(200)
        self.assertEqual(page.input_value("#f-location"), "")
        page.close()


if __name__ == "__main__":
    unittest.main()
