#!/bin/sh
# Met à jour ENQUÊTE-EPN sur le serveur : récupère le code, reconstruit, redémarre (les données sont conservées).
#   sudo sh deploiement/mettre-a-jour.sh
set -eu
cd "$(dirname "$0")/.."
# Publication par Cloudflare Tunnel si un jeton est réglé dans .env, sinon par Caddy (HTTPS direct).
if grep -q '^CLOUDFLARE_TUNNEL_TOKEN=..' .env 2>/dev/null; then
  COMPOSE="docker compose -f docker-compose.yml -f deploiement/docker-compose.cloudflare.yml"
else
  COMPOSE="docker compose -f docker-compose.yml -f deploiement/docker-compose.prod.yml"
fi

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
