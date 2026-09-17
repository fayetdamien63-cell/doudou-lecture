# 📚 Doudou Lecture

La bibliothèque de l'école maternelle : un petit site web **coloré**, **utilisable
au téléphone** et conçu pour tourner sur un **Raspberry Pi** à la maison.

- 🔎 **Chercher** un livre par titre, auteur, thème, personnage, animal… (les
  accents et les majuscules n'ont aucune importance : « elephant » trouve « Éléphant »)
- 📷 **Ajouter** un livre en scannant son code-barres : la fiche (titre, auteur,
  éditeur, résumé, couverture) est récupérée automatiquement sur Internet
- 📖 **Consulter** tout le contenu de la bibliothèque, avec les couvertures
- 🎒 **Prêter** un livre à un élève (prénom, classe, date de retour) et voir
  d'un coup d'œil les retards
- 🌈 Interface gaie, gros boutons, pensée pour une utilisation à une main

Techniquement : **Python 3 + Flask + SQLite**, aucune base de données à installer,
aucun `npm`, aucune compilation. L'ensemble tient dans une trentaine de méga-octets
de mémoire, ce qui passe sur un Raspberry Pi 1B+.

---

## Sommaire

1. [Essayer en 2 minutes](#1-essayer-en-2-minutes)
2. [Installation sur le Raspberry Pi](#2-installation-sur-le-raspberry-pi)
3. [Démarrage automatique (systemd)](#3-démarrage-automatique-systemd)
4. [Accès depuis l'extérieur avec Cloudflare Tunnel](#4-accès-depuis-lextérieur-avec-cloudflare-tunnel-étape-par-étape)
5. [Variante : hébergement gratuit sur PythonAnywhere](#5-variante--hébergement-gratuit-sur-pythonanywhere)
6. [Protéger l'accès](#6-protéger-laccès)
7. [Utilisation au quotidien](#7-utilisation-au-quotidien)
8. [Sauvegardes](#8-sauvegardes)
9. [Mise à jour](#9-mise-à-jour)
10. [Dépannage](#10-dépannage)
11. [Sous le capot](#11-sous-le-capot)

---

## 1. Essayer en 2 minutes

Sur n'importe quel ordinateur (Linux, macOS, Windows) avec Python 3.8 ou plus :

```bash
git clone https://github.com/fayetdamien63-cell/doudou-lecture.git
cd doudou-lecture
python3 -m venv .venv
source .venv/bin/activate          # Windows : .venv\Scripts\activate
pip install -r requirements.txt
python3 tools/donnees_exemple.py   # facultatif : quelques livres de démonstration
python3 app/app.py
```

Puis ouvrez <http://localhost:8000>.

> ⚠️ Le **scan par la caméra ne fonctionne qu'en `https://`** (ou sur
> `http://localhost`) : c'est une règle de sécurité des navigateurs. C'est
> exactement le problème que règle le tunnel Cloudflare de l'étape 4.

---

## 2. Installation sur le Raspberry Pi

### Matériel

| Modèle | Ça marche ? | Remarque |
|---|---|---|
| **Pi 1B+ / Zero** (512 Mo, ARMv6) | ✅ oui | Comptez 1 à 3 s d'affichage par page. Mettez `--workers 1` dans le service. |
| **Pi 3B+ / 4 / 5** | ✅ recommandé | Instantané, et `cloudflared` y est bien mieux supporté (voir étape 4). |

Une carte SD de 8 Go suffit largement : 1 000 livres avec leurs couvertures ≈ 150 Mo.

### Étapes

```bash
# 1. Outils de base (Raspberry Pi OS Lite convient parfaitement)
sudo apt update
sudo apt install -y python3 python3-venv python3-pip git sqlite3

# 2. Récupérer l'application dans le dossier de l'utilisateur pi
cd ~
git clone https://github.com/fayetdamien63-cell/doudou-lecture.git
cd doudou-lecture

# 3. Environnement Python isolé
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt

# 4. Premier essai
.venv/bin/python app/app.py
```

Depuis un autre appareil du réseau local, ouvrez `http://adresse-ip-du-pi:8000`
(`hostname -I` donne l'adresse). Arrêtez ensuite avec `Ctrl+C`.

La base de données et les couvertures sont créées automatiquement dans
`~/doudou-lecture/data/`.

---

## 3. Démarrage automatique (systemd)

Pour que l'application se lance toute seule au démarrage du Pi :

```bash
sudo cp ~/doudou-lecture/deploy/doudou-lecture.service /etc/systemd/system/
sudo nano /etc/systemd/system/doudou-lecture.service
```

Vérifiez / adaptez :

- `User=pi` et les chemins `/home/pi/doudou-lecture` (si votre utilisateur porte
  un autre nom, remplacez partout) ;
- `DOUDOU_PIN=1234` → **choisissez votre propre code d'accès** (laissez vide
  pour ne pas en demander) ;
- `DOUDOU_LOAN_DAYS=14` → durée de prêt proposée par défaut ;
- sur un **Pi 1B+**, remplacez `--workers 2` par `--workers 1`.

Puis :

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now doudou-lecture
systemctl status doudou-lecture      # doit afficher « active (running) »
curl -I http://127.0.0.1:8000        # doit répondre 200 ou 302
```

Les journaux se consultent avec `journalctl -u doudou-lecture -f`.

L'application n'écoute que sur `127.0.0.1` : elle n'est donc **pas** exposée
directement sur Internet, c'est le tunnel Cloudflare qui s'en charge.

---

## 4. Accès depuis l'extérieur avec Cloudflare Tunnel, étape par étape

`cloudflared` crée une sortie sécurisée depuis le Pi vers Cloudflare : **aucun port
à ouvrir sur la box**, pas d'adresse IP fixe à gérer, et un **certificat HTTPS
gratuit** (indispensable pour la caméra du téléphone).

### Prérequis

- Un compte Cloudflare gratuit : <https://dash.cloudflare.com/sign-up>
- Un nom de domaine dont les serveurs DNS pointent vers Cloudflare
  (ajout du domaine : *Add a site* dans le tableau de bord, puis suivre les
  instructions pour changer les DNS chez votre registrar). Un domaine coûte
  quelques euros par an ; c'est le seul frais.

### Étape 4.1 — Installer cloudflared sur le Pi

**Pi 3B+, 4 ou 5 (64 bits) :**

```bash
curl -L -o cloudflared.deb https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-arm64.deb
sudo dpkg -i cloudflared.deb && rm cloudflared.deb
```

**Pi 3B+ en 32 bits, ou Pi 2 :**

```bash
curl -L -o cloudflared.deb https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-arm.deb
sudo dpkg -i cloudflared.deb && rm cloudflared.deb
```

**Pi 1B+ / Zero (ARMv6) :** les binaires officiels ne sont pas garantis sur
ARMv6. Essayez la version `linux-arm` ci-dessus :

```bash
cloudflared --version
```

- Si la version s'affiche : parfait, continuez.
- Si vous obtenez `Illegal instruction` : ARMv6 n'est pas supporté. Deux
  solutions : héberger le tunnel sur un autre appareil du réseau
  (un Pi 3B+, un NAS, un vieux PC) qui pointera vers `http://IP-DU-PI:8000`
  — pensez alors à remplacer `--bind 127.0.0.1:8000` par `--bind 0.0.0.0:8000`
  dans le service —, ou simplement faire tourner l'application elle-même sur le
  Pi 3B+.

Vérification :

```bash
cloudflared --version
```

### Étape 4.2 — Se connecter à votre compte Cloudflare

```bash
cloudflared tunnel login
```

Une adresse s'affiche dans le terminal. Ouvrez-la dans le navigateur d'un
ordinateur ou d'un téléphone, connectez-vous, puis **choisissez votre domaine**
et validez. Un certificat est enregistré dans `~/.cloudflared/cert.pem`.

### Étape 4.3 — Créer le tunnel

```bash
cloudflared tunnel create bibliotheque
```

La commande affiche un **identifiant** du type
`6f1a2b3c-4d5e-6f70-8a9b-0c1d2e3f4a5b` et crée le fichier de clés
`~/.cloudflared/<ID>.json`. Notez cet identifiant, il sert aux étapes suivantes.

```bash
cloudflared tunnel list       # pour le retrouver plus tard
```

### Étape 4.4 — Associer un nom de domaine au tunnel

```bash
cloudflared tunnel route dns bibliotheque bibliotheque.mondomaine.fr
```

Cloudflare crée tout seul l'enregistrement DNS correspondant. Remplacez
`bibliotheque.mondomaine.fr` par le sous-domaine que vous voulez utiliser.

### Étape 4.5 — Écrire le fichier de configuration

```bash
sudo mkdir -p /etc/cloudflared
sudo cp ~/.cloudflared/*.json /etc/cloudflared/
sudo cp ~/doudou-lecture/deploy/cloudflared-config.yml /etc/cloudflared/config.yml
sudo nano /etc/cloudflared/config.yml
```

Remplacez `<ID-DU-TUNNEL>` (deux fois) et le nom d'hôte :

```yaml
tunnel: 6f1a2b3c-4d5e-6f70-8a9b-0c1d2e3f4a5b
credentials-file: /etc/cloudflared/6f1a2b3c-4d5e-6f70-8a9b-0c1d2e3f4a5b.json

originRequest:
  connectTimeout: 30s

ingress:
  - hostname: bibliotheque.mondomaine.fr
    service: http://127.0.0.1:8000
  - service: http_status:404
```

Test à blanc, en premier plan :

```bash
sudo cloudflared --config /etc/cloudflared/config.yml tunnel run bibliotheque
```

Ouvrez `https://bibliotheque.mondomaine.fr` depuis votre téléphone (en 4G, pour
bien vérifier que ça passe par Internet). Arrêtez ensuite avec `Ctrl+C`.

### Étape 4.6 — Lancer le tunnel automatiquement au démarrage

```bash
sudo cloudflared --config /etc/cloudflared/config.yml service install
sudo systemctl enable --now cloudflared
systemctl status cloudflared
```

Vérifications utiles :

```bash
journalctl -u cloudflared -f            # journal du tunnel
cloudflared tunnel info bibliotheque    # état des connexions
```

Et voilà : le site est accessible en HTTPS depuis n'importe où, la caméra
fonctionne, et le Raspberry Pi reste invisible depuis Internet. 🎉

### Étape 4.7 — Ajouter le site à l'écran d'accueil du téléphone

Sur Android (Chrome) : menu ⋮ → *Ajouter à l'écran d'accueil*.
Sur iPhone (Safari) : bouton Partager → *Sur l'écran d'accueil*.
L'application s'ouvre alors en plein écran, comme une vraie application.

---

## 5. Variante : hébergement gratuit sur PythonAnywhere

Pas de Raspberry Pi sous la main, ou envie d'un plan B si le Pi tombe en panne ?
**PythonAnywhere** héberge gratuitement l'application, sans carte bancaire.

**Ce qui marche sur le compte gratuit :** un espace disque conservé d'une fois sur
l'autre (512 Mo, soit environ 1 000 livres avec leurs couvertures), l'adresse
`https://votre-nom.pythonanywhere.com` en HTTPS — donc **le scan par la caméra
fonctionne** —, et l'accès aux trois sources utilisées pour les fiches
(`.googleapis.com`, `openlibrary.org`, `covers.openlibrary.org`), qui figurent sur
la liste blanche des comptes gratuits.

**Ce qu'il faut accepter :** un seul site, pas de nom de domaine personnalisé, un
quota de calcul quotidien (sans conséquence pour un usage d'école), et un bouton
« renouveler » à cliquer tous les 3 mois pour garder le compte actif.

> 🔒 **À peser avant de choisir.** L'application enregistre des **prénoms
> d'élèves**. Sur le Raspberry Pi, ces données restent physiquement dans l'école ;
> sur PythonAnywhere, elles sont confiées à un hébergeur tiers situé hors de
> France. Pour un usage durable, l'auto-hébergement reste préférable ; le compte
> gratuit est parfait pour **essayer l'application** ou **dépanner**.

### Étape 5.1 — Créer le compte

Inscrivez-vous sur <https://www.pythonanywhere.com/registration/register/beginner/>
(formule « Beginner », gratuite). Notez bien votre **nom d'utilisateur** : il
donnera l'adresse de votre site.

### Étape 5.2 — Récupérer l'application

Onglet **Consoles** → **Bash**, puis :

```bash
git clone https://github.com/fayetdamien63-cell/doudou-lecture.git
cd doudou-lecture
mkvirtualenv --python=/usr/bin/python3.13 doudou
pip install Flask
```

`mkvirtualenv` crée l'environnement et l'active (le nom `doudou` apparaît alors au
début de la ligne de commande). Si Python 3.13 n'existe pas sur votre compte,
prenez la version la plus récente proposée par `ls /usr/bin/python3.*`.

> `gunicorn` n'est pas nécessaire ici : PythonAnywhere lance lui-même
> l'application, d'où l'installation de `Flask` seul.

### Étape 5.3 — Créer le site web

Onglet **Web** → **Add a new web app** → **Next** → choisissez **Manual
configuration** (surtout pas « Flask », qui créerait un projet vide) → la même
version de Python qu'à l'étape précédente → **Next**.

### Étape 5.4 — Indiquer l'environnement virtuel

Toujours dans l'onglet **Web**, section **Virtualenv**, saisissez :

```
doudou
```

Le chemin complet `/home/<votre-nom>/.virtualenvs/doudou` s'affiche alors
automatiquement.

### Étape 5.5 — Remplir le fichier WSGI

Section **Code** de l'onglet **Web**, cliquez sur le lien
**WSGI configuration file** (`/var/www/<votre-nom>_pythonanywhere_com_wsgi.py`).
**Effacez tout** le contenu et remplacez-le par celui de
[`deploy/pythonanywhere_wsgi.py`](deploy/pythonanywhere_wsgi.py), en adaptant :

- `<votre-nom>` → votre nom d'utilisateur PythonAnywhere ;
- `DOUDOU_PIN` → **votre** code d'accès (le site est public !).

Les deux lignes `proxy.server:3128` sont indispensables sur un compte gratuit :
c'est par ce relais que passent les recherches d'ISBN. Enregistrez (**Save**).

### Étape 5.6 — Servir les images et les styles

Toujours dans l'onglet **Web**, section **Static files**, ajoutez une entrée :

| URL | Directory |
|---|---|
| `/static/` | `/home/<votre-nom>/doudou-lecture/app/static/` |

Ce n'est pas obligatoire, mais le site sera nettement plus rapide.

### Étape 5.7 — Démarrer

Cliquez sur le gros bouton vert **Reload**, puis ouvrez
`https://votre-nom.pythonanywhere.com`. Le code d'accès doit apparaître, puis le
catalogue (vide au départ).

Pour ajouter quelques livres de démonstration, dans une console Bash :

```bash
workon doudou
cd ~/doudou-lecture
DOUDOU_DATA=~/doudou-lecture/data python3 tools/donnees_exemple.py
```

### Étape 5.8 — Sauvegarde automatique (facultatif)

Le compte gratuit autorise **une tâche quotidienne**. Onglet **Tasks**, ajoutez à
l'heure de votre choix :

```
/home/<votre-nom>/doudou-lecture/deploy/sauvegarde.sh /home/<votre-nom>/sauvegardes
```

Les fichiers créés se téléchargent ensuite depuis l'onglet **Files**.

### Mettre à jour plus tard

```bash
workon doudou
cd ~/doudou-lecture && git pull && pip install -r requirements.txt
```

Puis **Reload** dans l'onglet **Web**. Le dossier `data/` n'est jamais touché :
vos livres et vos prêts sont conservés.

### Si quelque chose cloche

| Symptôme | Cause la plus fréquente |
|---|---|
| Page « Something went wrong » | Regardez le **Error log** (onglet Web) : c'est presque toujours un `<votre-nom>` oublié dans le fichier WSGI. |
| « Livre introuvable en ligne » pour **tous** les livres | Les lignes `proxy.server:3128` manquent dans le fichier WSGI, ou le compte est payant et elles doivent au contraire être retirées. |
| Le site répond mais sans couleurs | L'entrée **Static files** de l'étape 5.6 est absente ou mal orthographiée (le `/` final compte). |
| Le site s'est éteint tout seul | Compte gratuit non renouvelé : reconnectez-vous et cliquez sur le bouton de renouvellement affiché dans l'onglet Web. |

---

## 6. Protéger l'accès

Un site en ligne est visible de tous : protégez-le, au choix (ou les deux).

**a) Le code d'accès intégré** — variable `DOUDOU_PIN` du service systemd.
Simple et suffisant pour une petite école : un seul code, partagé entre les
maîtresses, mémorisé 30 jours sur le téléphone.

**b) Cloudflare Access** (gratuit jusqu'à 50 utilisateurs, plus solide) —
dans le tableau de bord Cloudflare : *Zero Trust → Access → Applications →
Add an application → Self-hosted*, indiquez `bibliotheque.mondomaine.fr`, puis
créez une règle « Emails » listant les adresses autorisées. Chaque personne
reçoit un code à usage unique par mail pour se connecter.

---

## 7. Utilisation au quotidien

### Ajouter un livre

1. Onglet **Ajouter** → bouton **📷 Scanner** → autorisez la caméra.
2. Visez le code-barres au dos du livre : un bip, et la fiche se remplit toute
   seule (titre, auteur, éditeur, résumé, couverture).
3. Touchez les **étiquettes** qui correspondent (thèmes, personnages, animaux) —
   ce sont elles qui rendront le livre facile à retrouver. Le champ
   « Nouveau… » permet d'en créer d'autres (dinosaure, école, doudou…).
4. **💾 Enregistrer**. Le formulaire se vide : livre suivant !

Pas de code-barres, ou livre introuvable en ligne ? Utilisez
*« Pas de code-barres ? Chercher par titre »*, ou remplissez simplement la fiche
à la main.

> Les informations viennent de **Google Books** puis d'**Open Library**, deux
> sources gratuites et sans inscription. Les couvertures sont **recopiées sur le
> Pi** : le catalogue s'affiche donc vite, même sans Internet.

### Chercher un livre

Tapez n'importe quoi dans la barre de recherche : titre, auteur, éditeur, mot du
résumé, étiquette, lieu de rangement, ISBN. Les résultats s'affichent au fur et à
mesure de la frappe. Les pastilles colorées filtrent par thème, et les listes
déroulantes par disponibilité (disponibles / empruntés / en retard).

### Prêter et rendre

Sur la fiche d'un livre : prénom de l'élève (les prénoms déjà saisis sont
proposés), classe, date du jour et date de retour pré-remplies → **🎒 Prêter**.
L'onglet **Emprunts** liste les prêts en cours, signale les retards en rouge et
permet de valider un retour d'un seul bouton. L'historique de chaque livre est
conservé sur sa fiche.

---

## 8. Sauvegardes

Toutes les données tiennent dans le dossier `data/` (base SQLite + couvertures).
Le script fourni en fait une copie datée et ne garde que les 8 dernières :

```bash
~/doudou-lecture/deploy/sauvegarde.sh            # vers ~/sauvegardes
~/doudou-lecture/deploy/sauvegarde.sh /mnt/cle   # ou vers une clé USB
```

Automatisation tous les dimanches à 3 h (`crontab -e`) :

```cron
0 3 * * 0 /home/pi/doudou-lecture/deploy/sauvegarde.sh
```

Pour restaurer : arrêtez le service, remettez le fichier `.db` en place sous le
nom `data/bibliotheque.db`, décompressez les couvertures, redémarrez.

---

## 9. Mise à jour

```bash
cd ~/doudou-lecture
git pull
.venv/bin/pip install -r requirements.txt
sudo systemctl restart doudou-lecture
```

Vos livres et vos prêts ne sont pas touchés (le dossier `data/` n'est jamais
versionné).

---

## 10. Dépannage

| Problème | Solution |
|---|---|
| **La caméra ne s'ouvre pas** | Le site doit être en `https://` (tunnel Cloudflare) ou en `http://localhost`. Vérifiez aussi l'autorisation « Caméra » du navigateur pour ce site. |
| **iPhone : le scan ne démarre pas** | Utilisez Safari. La bibliothèque de secours ZXing se télécharge alors depuis Internet ; pour un fonctionnement hors ligne, placez le fichier `index.min.js` de `@zxing/library` dans `app/static/js/vendor/zxing.min.js`. |
| **« Livre introuvable en ligne »** | Beaucoup d'albums jeunesse français ne sont pas référencés. Remplissez la fiche à la main : c'est deux champs, et la recherche fonctionnera pareil. |
| **Pas de couverture** | Collez l'adresse d'une image (clic droit → « Copier l'adresse de l'image ») dans le champ prévu : elle sera copiée sur le Pi. |
| **Le site répond « 502 » via le tunnel** | L'application n'est pas démarrée : `sudo systemctl restart doudou-lecture`, puis `journalctl -u doudou-lecture -n 50`. |
| **Le tunnel ne démarre pas** | `journalctl -u cloudflared -n 50`. Vérifiez l'ID du tunnel et le chemin du fichier `.json` dans `/etc/cloudflared/config.yml`. |
| **C'est lent (Pi 1B+)** | Passez à `--workers 1 --threads 4` dans le service, et évitez d'afficher des milliers de livres d'un coup (la recherche filtre côté serveur). |
| **J'ai oublié le code d'accès** | Modifiez `DOUDOU_PIN` dans `/etc/systemd/system/doudou-lecture.service`, puis `sudo systemctl daemon-reload && sudo systemctl restart doudou-lecture`. |

---

## 11. Sous le capot

```
app/
  app.py          routes web et API JSON
  db.py           schéma SQLite et requêtes
  metadata.py     recherche ISBN (Google Books, Open Library) et couvertures
  templates/      pages HTML (Jinja2)
  static/         CSS, JavaScript, icône
deploy/           services systemd, modèles cloudflared et PythonAnywhere, sauvegarde
tools/            jeu de données d'exemple
tests/            tests automatiques (sans accès réseau)
data/             base de données et couvertures (créé au premier lancement)
```

### Réglages (variables d'environnement)

| Variable | Défaut | Rôle |
|---|---|---|
| `DOUDOU_DATA` | `./data` | Dossier de la base et des couvertures |
| `DOUDOU_PIN` | *(vide)* | Code d'accès ; vide = pas de code demandé |
| `DOUDOU_LOAN_DAYS` | `14` | Durée de prêt proposée par défaut |
| `DOUDOU_PORT` | `8000` | Port d'écoute (mode développement) |
| `DOUDOU_HOST` | `0.0.0.0` | Interface d'écoute (mode développement) |

### API JSON

| Méthode | Route | Rôle |
|---|---|---|
| `GET` | `/api/livres?q=&tag=&statut=&tri=` | Liste / recherche |
| `POST` | `/api/livres` | Ajouter un livre |
| `PUT` | `/api/livres/<id>` | Modifier |
| `DELETE` | `/api/livres/<id>` | Supprimer |
| `GET` | `/api/lookup?isbn=` | Fiche trouvée en ligne |
| `GET` | `/api/recherche-titre?q=` | Recherche en ligne par titre |
| `POST` | `/api/emprunts` | Prêter un livre |
| `POST` | `/api/emprunts/<id>/retour` | Enregistrer un retour |
| `GET` | `/api/tags`, `/api/eleves`, `/api/stats` | Étiquettes, prénoms, chiffres |

### Tests

```bash
python3 -m unittest discover -s tests
```

---

## Licence

MIT — voir [LICENSE](LICENSE). Bonne lecture à tous les petits ! 🦊📖
