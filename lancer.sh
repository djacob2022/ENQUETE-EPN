#!/bin/sh
# Lance ENQUÊTE-EPN en local avec Docker (macOS / Linux).
# Usage : ./lancer.sh          démarre (et construit au premier lancement)
#         ./lancer.sh arreter  arrête les conteneurs (les données sont conservées)
#         ./lancer.sh effacer  arrête et SUPPRIME toutes les données (base, fichiers)
set -e
cd "$(dirname "$0")"

if ! docker info >/dev/null 2>&1; then
  echo "Docker n'est pas démarré. Lancez Docker Desktop puis relancez ce script." >&2
  exit 1
fi

case "$1" in
  arreter) docker compose --profile dev stop; exit 0 ;;
  effacer) docker compose --profile dev down -v; exit 0 ;;
esac

if [ ! -f .env ]; then
  aleatoire() { LC_ALL=C tr -dc 'A-Za-z0-9' </dev/urandom | head -c "$1"; }
  MDP_ADMIN=$(aleatoire 14)
  sed -e "s|^DJANGO_SECRET_KEY=.*|DJANGO_SECRET_KEY=$(aleatoire 50)|" \
      -e "s|^DJANGO_SUPERUSER_PASSWORD=.*|DJANGO_SUPERUSER_PASSWORD=$MDP_ADMIN|" \
      -e "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=$(aleatoire 24)|" \
      -e "s|^COOKIES_SECURE=.*|COOKIES_SECURE=0|" \
      -e "s|^CHARGER_DONNEES_DEMO=.*|CHARGER_DONNEES_DEMO=1|" \
      .env.example > .env
  echo "Fichier .env créé pour un test sur ce poste (données de démonstration, http). Identifiants administrateur : admin / $MDP_ADMIN (notez-les)."
fi

docker compose --profile dev up -d --build
echo
echo "Patientez une vingtaine de secondes au premier lancement, puis ouvrez :"
echo "  Espace administrateur : http://localhost:8000/connexion/  (identifiants dans .env)"
echo "  E-mails envoyés (test) : http://localhost:8025"
echo "Journal de l'application : docker compose logs -f web"
