#!/bin/sh
# Installation d'ENQUÊTE-EPN sur un serveur Ubuntu 22.04 ou 24.04, à lancer depuis le dossier du projet :
#   sudo sh deploiement/installer.sh
# Le script installe Docker, ouvre le pare-feu (SSH, HTTP, HTTPS), crée la configuration de production,
# vérifie le domaine, puis démarre l'application avec un certificat HTTPS automatique.
set -eu
cd "$(dirname "$0")/.."
COMPOSE="docker compose -f docker-compose.yml -f deploiement/docker-compose.prod.yml"

[ "$(id -u)" -eq 0 ] || { echo "Lancez ce script avec sudo." >&2; exit 1; }
. /etc/os-release
[ "${ID:-}" = "ubuntu" ] || echo "Attention : script prévu pour Ubuntu (système détecté : ${ID:-inconnu})."

echo "== 1/6 Docker"
if ! command -v docker >/dev/null 2>&1; then
  apt-get update -q && apt-get install -y -q ca-certificates curl
  curl -fsSL https://get.docker.com | sh
fi
docker compose version >/dev/null

echo "== 2/6 Pare-feu : SSH, HTTP et HTTPS seulement"
if command -v ufw >/dev/null 2>&1; then
  ufw allow OpenSSH >/dev/null; ufw allow 80/tcp >/dev/null; ufw allow 443/tcp >/dev/null; ufw allow 443/udp >/dev/null
  ufw --force enable >/dev/null
fi

echo "== 3/6 Configuration de production (.env)"
aleatoire() { LC_ALL=C tr -dc 'A-Za-z0-9' </dev/urandom | head -c "$1"; }
# Remplace la ligne CLE=… de .env, sans interpréter la valeur (mots de passe avec | & / etc.).
# « $ » est doublé : Docker Compose l'interpréterait sinon comme une variable.
definir() {
  valeur=$(printf '%s' "$2" | sed 's/\$/$$/g')
  grep -v "^$1=" .env > .env.tmp || true
  printf '%s=%s\n' "$1" "$valeur" >> .env.tmp
  mv .env.tmp .env
}
if [ -f .env ]; then
  echo ".env existe déjà : conservé tel quel."
else
  printf "Nom de domaine du site (ex. enquete.mon-ministere.ci) : "; read -r DOMAINE
  printf "E-mail du service informatique (alertes du certificat) : "; read -r EMAIL_ADMIN
  printf "Serveur SMTP (ex. smtp-relay.brevo.com) : "; read -r SMTP_HOTE
  printf "Port SMTP [587] : "; read -r SMTP_PORT; SMTP_PORT=${SMTP_PORT:-587}
  printf "Identifiant SMTP : "; read -r SMTP_UTILISATEUR
  printf "Mot de passe SMTP : "; stty -echo 2>/dev/null || true; read -r SMTP_MDP; stty echo 2>/dev/null || true; echo
  printf "Adresse d'expédition (ex. enquete@mon-ministere.ci) : "; read -r EXPEDITEUR
  MDP_ADMIN=$(aleatoire 16)
  umask 077
  grep -v '^#' deploiement/env.production.exemple | grep -v '^$' > .env
  definir DOMAINE "$DOMAINE"
  definir SITE_URL "https://$DOMAINE"
  definir DJANGO_ALLOWED_HOSTS "$DOMAINE"
  definir DJANGO_CSRF_TRUSTED_ORIGINS "https://$DOMAINE"
  definir EMAIL_ADMIN "$EMAIL_ADMIN"
  definir DJANGO_SUPERUSER_EMAIL "$EMAIL_ADMIN"
  definir DJANGO_SECRET_KEY "$(aleatoire 60)"
  definir DJANGO_SUPERUSER_PASSWORD "$MDP_ADMIN"
  definir POSTGRES_PASSWORD "$(aleatoire 32)"
  definir EMAIL_HOST "$SMTP_HOTE"
  definir EMAIL_PORT "$SMTP_PORT"
  definir EMAIL_HOST_USER "$SMTP_UTILISATEUR"
  definir EMAIL_HOST_PASSWORD "$SMTP_MDP"
  definir DEFAULT_FROM_EMAIL "Enquête EPN <$EXPEDITEUR>"
  chmod 600 .env
  echo "Fichier .env créé (lisible par root seulement)."
  echo "Pensez à y renseigner PAYS, DEVISE, NOM_MINISTERE et NOM_INSTITUTION (en-tête officiel)."
fi
DOMAINE=$(sed -n 's/^DOMAINE=//p' .env)

echo "== 4/6 Vérification du domaine"
IP_DOMAINE=$(getent hosts "$DOMAINE" | awk '{print $1}' | head -1 || true)
IPS_SERVEUR=$(hostname -I 2>/dev/null || true)
echo "  $DOMAINE pointe vers : ${IP_DOMAINE:-introuvable}"
echo "  adresses de ce serveur : $IPS_SERVEUR"
if [ -z "$IP_DOMAINE" ]; then
  echo "  Le domaine ne résout pas encore. Créez l'enregistrement DNS A vers l'adresse publique du serveur,"
  echo "  attendez sa propagation, puis relancez ce script. (Sans cela, le certificat HTTPS ne peut pas être obtenu.)"
  exit 1
fi

echo "== 5/6 Construction et validation"
$COMPOSE build
$COMPOSE run --rm --no-deps caddy caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile

echo "== 6/6 Démarrage"
$COMPOSE up -d
printf "  Attente de l'application"
for i in $(seq 1 60); do
  if $COMPOSE exec -T web python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/sante/', timeout=3)" 2>/dev/null; then
    echo " : prête."; break
  fi
  printf "."; sleep 2
done
$COMPOSE exec -T web python manage.py check --deploy --fail-level ERROR || true

echo
echo "Installation terminée."
echo "  Lien à diffuser aux EPN : https://$DOMAINE/formulaire"
echo "  Espace administrateur   : https://$DOMAINE/connexion"
if [ -n "${MDP_ADMIN:-}" ]; then
  echo "  Identifiants            : admin / $MDP_ADMIN   (notez-les, puis changez le mot de passe)"
else
  echo "  Identifiants            : voir DJANGO_SUPERUSER_USERNAME / DJANGO_SUPERUSER_PASSWORD dans .env"
fi
echo "  Le certificat HTTPS est obtenu à la première visite (quelques secondes)."
