"""Contrôles au démarrage : réglages de démonstration oubliés en production."""
import os

from django.conf import settings
from django.core.checks import Warning, register


@register()
def reglages_de_production(app_configs, **kwargs):
    if settings.DEBUG:
        return []
    alertes = []
    https = settings.SITE_URL.startswith("https://")
    if os.environ.get("CHARGER_DONNEES_DEMO") == "1":
        alertes.append(Warning(
            "Les données de démonstration sont chargées (CHARGER_DONNEES_DEMO=1).",
            hint="En production, mettez CHARGER_DONNEES_DEMO=0 : des EPN et réponses fictifs fausseraient les statistiques.",
            id="enquete.W001"))
    if https and not settings.SESSION_COOKIE_SECURE:
        alertes.append(Warning(
            "Le site est en HTTPS mais les cookies de session peuvent circuler en clair (COOKIES_SECURE=0).",
            hint="Mettez COOKIES_SECURE=1.", id="enquete.W002"))
    if https and "mailpit" in settings.EMAIL_HOST:
        alertes.append(Warning(
            "Les e-mails partent vers Mailpit (serveur de test) : les EPN ne les recevront pas.",
            hint="Renseignez le serveur SMTP réel (EMAIL_HOST…) et démarrez sans --profile dev.", id="enquete.W003"))
    return alertes
