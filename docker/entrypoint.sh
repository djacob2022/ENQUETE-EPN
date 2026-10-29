#!/bin/sh
# Démarrage du conteneur web : migrations, compte administrateur initial, données de démo éventuelles.
set -e

python manage.py migrate --noinput

if [ -n "$DJANGO_SUPERUSER_USERNAME" ] && [ -n "$DJANGO_SUPERUSER_PASSWORD" ]; then
  python manage.py createsuperuser --noinput \
    --username "$DJANGO_SUPERUSER_USERNAME" --email "${DJANGO_SUPERUSER_EMAIL:-admin@example.org}" 2>/dev/null \
    || echo "Compte administrateur « $DJANGO_SUPERUSER_USERNAME » déjà présent."
fi

if [ "$CHARGER_DONNEES_DEMO" = "1" ]; then
  python manage.py donnees_demo
fi

exec "$@"
