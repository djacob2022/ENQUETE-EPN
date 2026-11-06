#!/bin/sh
# Restaure une sauvegarde (base de données + pièces jointes).
#   sudo sh deploiement/restaurer.sh                      → liste les sauvegardes disponibles
#   sudo sh deploiement/restaurer.sh 2026-11-03_0200      → restaure celle de cette date
set -eu
cd "$(dirname "$0")/.."
# Publication par Cloudflare Tunnel si un jeton est réglé dans .env, sinon par Caddy (HTTPS direct).
if grep -q '^CLOUDFLARE_TUNNEL_TOKEN=..' .env 2>/dev/null; then
  COMPOSE="docker compose -f docker-compose.yml -f deploiement/docker-compose.cloudflare.yml"
else
  COMPOSE="docker compose -f docker-compose.yml -f deploiement/docker-compose.prod.yml"
fi
# Base hébergée (Supabase) si DATABASE_URL est réglé dans .env.
if grep -q '^DATABASE_URL=..' .env 2>/dev/null; then
  COMPOSE="$COMPOSE -f deploiement/docker-compose.supabase.yml"
fi

if [ $# -eq 0 ]; then
  echo "Sauvegardes disponibles :"
  $COMPOSE exec -T backup sh -c 'ls -1 /backups | sed -n "s/^enquete_\(.*\)\.dump$/  \1/p"'
  echo "Relancez avec la date choisie, par exemple : sudo sh deploiement/restaurer.sh 2026-11-03_0200"
  exit 0
fi
DATE=$1
$COMPOSE exec -T backup test -f "/backups/enquete_$DATE.dump" || { echo "Sauvegarde enquete_$DATE.dump introuvable." >&2; exit 1; }

printf "La base et les pièces jointes actuelles seront REMPLACÉES par la sauvegarde du %s. Continuer ? (oui/non) " "$DATE"
read -r REPONSE
[ "$REPONSE" = "oui" ] || { echo "Abandon."; exit 1; }

echo "== Arrêt de l'application"
$COMPOSE stop web
echo "== Base de données"
$COMPOSE exec -T -e FICHIER="/backups/enquete_$DATE.dump" backup sh -c 'pg_restore --clean --if-exists --no-owner -d "${DATABASE_URL:-$PGDATABASE}" "$FICHIER"' \
  || echo "  (pg_restore a signalé des avertissements : vérifiez l'application après redémarrage)"
echo "== Pièces jointes"
if $COMPOSE exec -T backup test -f "/backups/pieces_$DATE.tar.gz"; then
  docker run --rm -v enquete-epn_media:/media -v enquete-epn_backups:/backups:ro alpine:3.20 \
    sh -c "find /media -mindepth 1 -delete && tar -xzf /backups/pieces_$DATE.tar.gz -C /media"
fi
echo "== Redémarrage"
$COMPOSE start web
echo "Restauration terminée."
