"""Paramètres Django de l'application ENQUÊTE-EPN.

Toute la configuration sensible passe par des variables d'environnement
(voir .env.example) afin que la même image Docker serve en recette et en production.
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def env_bool(name, default=False):
    return os.environ.get(name, str(default)).lower() in ("1", "true", "yes", "oui")


def env_list(name, default=""):
    return [v.strip() for v in os.environ.get(name, default).split(",") if v.strip()]


DEBUG = env_bool("DJANGO_DEBUG", False)
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "")
if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = "dev-uniquement-ne-pas-utiliser-en-production"
    else:
        raise RuntimeError("DJANGO_SECRET_KEY doit être défini quand DJANGO_DEBUG=0.")

ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")

# Adresse publique utilisée pour construire les liens envoyés par e-mail.
SITE_URL = os.environ.get("SITE_URL", "http://localhost:8000").rstrip("/")
# Nombre de proxys de confiance devant l'application (Nginx, Traefik…) : 0 = accès direct.
# Sert à retrouver l'adresse IP réelle du visiteur dans X-Forwarded-For pour la limite anti-abus.
NB_PROXYS_DE_CONFIANCE = int(os.environ.get("NB_PROXYS_DE_CONFIANCE", "0"))
NOM_INSTITUTION = os.environ.get("NOM_INSTITUTION", "[Nom de l'institution de tutelle]")
# Identité officielle affichée dans l'en-tête de toutes les pages (à adapter dans .env).
PAYS = os.environ.get("PAYS", "République de [Pays]")
DEVISE = os.environ.get("DEVISE", "[Devise nationale]")
NOM_MINISTERE = os.environ.get("NOM_MINISTERE", "[Ministère de tutelle]")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "enquete",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "enquete.securite.LimiteTailleRequete",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

if os.environ.get("POSTGRES_HOST"):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "HOST": os.environ["POSTGRES_HOST"],
            "PORT": os.environ.get("POSTGRES_PORT", "5432"),
            "NAME": os.environ.get("POSTGRES_DB", "enquete"),
            "USER": os.environ.get("POSTGRES_USER", "enquete"),
            "PASSWORD": os.environ.get("POSTGRES_PASSWORD", ""),
            "CONN_MAX_AGE": 60,
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

# Blocage temporaire après des mots de passe erronés répétés (API et /django-admin/).
AUTHENTICATION_BACKENDS = ["enquete.securite.AuthentificationProtegee"]

# Plus gros envoi accepté : une pièce jointe de 10 Mo plus l'enveloppe de la requête.
TAILLE_MAX_REQUETE = 12 * 1024 * 1024

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 10}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "fr-fr"
TIME_ZONE = os.environ.get("TIME_ZONE", "Africa/Abidjan")
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
# Fichiers construits par Vite (frontend/dist/assets → /static/assets/…).
STATICFILES_DIRS = [p for p in [BASE_DIR / "frontend" / "dist"] if p.exists()]
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"
        if not DEBUG
        else "django.contrib.staticfiles.storage.StaticFilesStorage"
    },
}

# Pièces jointes : jamais servies directement, uniquement via les vues de téléchargement contrôlées.
MEDIA_ROOT = Path(os.environ.get("MEDIA_ROOT", BASE_DIR / "media"))
FILE_UPLOAD_PERMISSIONS = 0o640
DATA_UPLOAD_MAX_NUMBER_FILES = 10

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# CSRF : le jeton est lu dans le cookie par l'interface React et renvoyé dans l'en-tête X-CSRFToken.
CSRF_COOKIE_HTTPONLY = False
SESSION_COOKIE_AGE = 60 * 60 * 8

# E-mails : SMTP configurable ; en développement, Mailpit (voir docker-compose.yml).
EMAIL_BACKEND = os.environ.get("EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend")
EMAIL_HOST = os.environ.get("EMAIL_HOST", "localhost")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "25"))
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", False)
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "ENQUETE-EPN <no-reply@enquete-epn.local>")

if not DEBUG:
    SESSION_COOKIE_SECURE = env_bool("COOKIES_SECURE", True)
    CSRF_COOKIE_SECURE = env_bool("COOKIES_SECURE", True)
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = "DENY"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    # Les liens personnels (/r/<jeton>/) n'apparaissent jamais en clair dans les journaux.
    "filters": {"jetons": {"()": "enquete.journaux.FiltreJetons"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "filters": ["jetons"]}},
    "root": {"handlers": ["console"], "level": os.environ.get("LOG_LEVEL", "INFO")},
}
