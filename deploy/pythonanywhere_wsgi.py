"""Modèle de fichier WSGI pour un hébergement gratuit sur PythonAnywhere.

À recopier dans le fichier proposé par l'onglet « Web » de PythonAnywhere
(/var/www/<votre-nom>_pythonanywhere_com_wsgi.py), en remplaçant partout
<votre-nom> par votre nom d'utilisateur PythonAnywhere.

Le contenu existant de ce fichier peut être entièrement supprimé.
"""

import os
import sys

# 1. Où se trouve l'application (le dossier cloné avec git).
PROJET = "/home/<votre-nom>/doudou-lecture"
if PROJET not in sys.path:
    sys.path.insert(0, PROJET)

# 2. Réglages. Le dossier « data » contient la base et les couvertures :
#    il est conservé d'un redémarrage à l'autre.
os.environ["DOUDOU_DATA"] = PROJET + "/data"
os.environ["DOUDOU_PIN"] = "1234"        # ⚠️ mettez votre propre code d'accès
os.environ["DOUDOU_LOAN_DAYS"] = "14"

# 3. Comptes GRATUITS uniquement : les accès à Internet passent par un proxy.
#    Sans cette ligne, la recherche des livres par ISBN ne fonctionnerait pas.
#    ➜ Supprimez ces deux lignes si vous passez sur un compte payant.
os.environ.setdefault("http_proxy", "http://proxy.server:3128")
os.environ.setdefault("https_proxy", "http://proxy.server:3128")

# 4. L'application elle-même. PythonAnywhere attend une variable nommée
#    « application » (et surtout pas d'appel à app.run()).
from app.app import app as application  # noqa: E402
