#!/bin/sh
# Sauvegarde de la base et des couvertures dans ~/sauvegardes.
# Exemple de tache cron (tous les dimanches a 3h) :
#   0 3 * * 0 /home/pi/doudou-lecture/deploy/sauvegarde.sh
set -eu

SOURCE="${DOUDOU_DATA:-/home/pi/doudou-lecture/data}"
DESTINATION="${1:-/home/pi/sauvegardes}"
HORODATAGE="$(date +%Y-%m-%d)"

mkdir -p "$DESTINATION"

# sqlite3 .backup fonctionne meme si l'application ecrit en meme temps.
if command -v sqlite3 >/dev/null 2>&1; then
    sqlite3 "$SOURCE/bibliotheque.db" ".backup '$DESTINATION/bibliotheque-$HORODATAGE.db'"
else
    cp "$SOURCE/bibliotheque.db" "$DESTINATION/bibliotheque-$HORODATAGE.db"
fi

tar -czf "$DESTINATION/couvertures-$HORODATAGE.tar.gz" -C "$SOURCE" covers

# On ne garde que les 8 dernieres sauvegardes.
ls -1t "$DESTINATION"/bibliotheque-*.db 2>/dev/null | tail -n +9 | xargs -r rm -f
ls -1t "$DESTINATION"/couvertures-*.tar.gz 2>/dev/null | tail -n +9 | xargs -r rm -f

echo "Sauvegarde terminee dans $DESTINATION"
