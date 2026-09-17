"""Ajoute quelques livres d'exemple pour essayer l'application.

    python3 tools/donnees_exemple.py

À ne lancer que sur une base de test : les livres sont ajoutés à la suite
de ceux qui existent déjà (les doublons d'ISBN sont ignorés).
"""

import os
import sys
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.app import app  # noqa: E402
from app import db as store  # noqa: E402

LIVRES = [
    {
        "title": "Le loup qui voulait changer de couleur",
        "authors": "Orianne Lallemand, Éléonore Thuillier",
        "publisher": "Auzou", "year": "2009", "isbn": "9782733808665",
        "summary": "Monsieur Loup n'aime pas sa couleur et essaie toutes les autres.",
        "location": "Bac bleu", "age_min": 3, "age_max": 6,
        "tags": [{"name": "Loup", "kind": "personnage"}, {"name": "Émotions", "kind": "theme"}],
    },
    {
        "title": "La chenille qui fait des trous",
        "authors": "Eric Carle", "publisher": "Mijade", "year": "1969",
        "summary": "Une petite chenille très affamée grignote tout sur son passage.",
        "location": "Bac vert", "age_min": 2, "age_max": 5,
        "tags": [{"name": "Nature", "kind": "theme"}, {"name": "Nourriture", "kind": "theme"}],
    },
    {
        "title": "Bonne nuit tout le monde",
        "authors": "Chris Haughton", "publisher": "Thierry Magnier", "year": "2016",
        "summary": "Le soleil se couche, tous les animaux de la forêt vont dormir… sauf Petit Ours.",
        "location": "Coin lecture", "age_min": 2, "age_max": 4,
        "tags": [{"name": "Nuit / Dodo", "kind": "theme"}, {"name": "Ours", "kind": "animal"}],
    },
    {
        "title": "Le machin",
        "authors": "Stéphane Servant, Cécile Bonbon", "publisher": "Didier Jeunesse",
        "year": "2010", "location": "Bac rouge", "age_min": 3, "age_max": 6,
        "summary": "Les animaux se demandent à quoi peut bien servir ce drôle de machin.",
        "tags": [{"name": "Animaux", "kind": "theme"}, {"name": "Éléphant", "kind": "animal"}],
    },
    {
        "title": "Va-t'en, Grand Monstre Vert !",
        "authors": "Ed Emberley", "publisher": "Kaléidoscope", "year": "1996",
        "summary": "On fabrique un monstre page après page… puis on le fait disparaître.",
        "location": "Bac jaune", "age_min": 3, "age_max": 6,
        "tags": [{"name": "Monstre", "kind": "personnage"}, {"name": "Émotions", "kind": "theme"}],
    },
]


def main():
    with app.app_context():
        for livre in LIVRES:
            if livre.get("isbn") and store.find_by_isbn(livre["isbn"]):
                print("déjà présent :", livre["title"])
                continue
            book_id = store.save_book(livre)
            print("ajouté :", livre["title"])
        # Un prêt en cours et un prêt en retard, pour voir l'affichage.
        books = store.list_books(limit=5)
        if len(books) >= 2:
            try:
                store.create_loan(
                    books[0]["id"], "Camille", "Grande section",
                    date.today().isoformat(),
                    (date.today() + timedelta(days=14)).isoformat(),
                )
                store.create_loan(
                    books[1]["id"], "Noé", "Petite section",
                    (date.today() - timedelta(days=20)).isoformat(),
                    (date.today() - timedelta(days=6)).isoformat(),
                )
            except ValueError:
                pass
    print("Terminé. Lancez l'application puis ouvrez http://localhost:8000")


if __name__ == "__main__":
    main()
