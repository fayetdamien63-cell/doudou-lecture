"""Préparation commune aux tests : un dossier de données temporaire unique.

L'application crée son objet Flask au moment de l'import, avec le dossier
indiqué par DOUDOU_DATA. Les modules de tests doivent donc partager le même
dossier et ne le supprimer qu'à la toute fin du processus — sinon le premier
module terminé effacerait la base utilisée par les suivants.
"""

import atexit
import os
import shutil
import sys
import tempfile

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if RACINE not in sys.path:
    sys.path.insert(0, RACINE)

if not os.environ.get("DOUDOU_DATA_TESTS"):
    dossier = tempfile.mkdtemp(prefix="doudou-tests-")
    os.environ["DOUDOU_DATA_TESTS"] = dossier
    atexit.register(shutil.rmtree, dossier, True)

DATA = os.environ["DOUDOU_DATA_TESTS"]
os.environ["DOUDOU_DATA"] = DATA
os.environ["DOUDOU_PIN"] = ""
