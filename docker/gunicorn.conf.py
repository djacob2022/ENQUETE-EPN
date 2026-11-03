"""Configuration Gunicorn : journal d'accès sans les jetons des liens personnels."""
import os
import sys

from gunicorn.glogging import Logger

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from enquete.journaux import masquer_jetons  # noqa: E402

bind = "0.0.0.0:8000"
workers = 3
accesslog = "-"


class JournalSansJetons(Logger):
    def atoms(self, resp, req, environ, request_time):
        atomes = super().atoms(resp, req, environ, request_time)
        # r = ligne de requête, U = chemin, f = page d'origine (Referer), {...}e = variables d'environnement.
        return {k: masquer_jetons(v) for k, v in atomes.items()}


logger_class = JournalSansJetons
