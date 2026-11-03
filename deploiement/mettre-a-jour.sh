#!/bin/sh
# Met à jour ENQUÊTE-EPN sur le serveur : récupère le code, reconstruit, redémarre (les données sont conservées).
#   sudo sh deploiement/mettre-a-jour.sh
set -eu
cd "$(dirname "$0")/.."
COMPOSE="docker compose -f docker-compose.yml -f deploiement/docker-compose.prod.yml"

echo "== Sauvegarde de précaution"
$COMPOSE exec -T backup sh -c 'jour=avant-maj_$(date +%Y-%m-%d_%H%M); pg_dump -Fc > /backups/enquete_$jour.dump && tar -czf /backups/pieces_$jour.tar.gz -C /media . && echo "  /backups/enquete_$jour.dump"'

echo "== Récupération du code"
git pull --ff-only

echo "== Reconstruction et redémarrage"
$COMPOSE build
$COMPOSE up -d
$COMPOSE exec -T web python manage.py check --deploy --fail-level ERROR || true
docker image prune -f >/dev/null
echo "Mise à jour terminée."
