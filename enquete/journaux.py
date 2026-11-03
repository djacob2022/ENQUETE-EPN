"""Filtre de journalisation : les liens personnels (/r/<jeton>/) n'apparaissent jamais en clair.

Module volontairement sans dépendance à Django : il est chargé avec la configuration des journaux, avant les
applications (Django) et par Gunicorn (docker/gunicorn.conf.py).
"""
import logging
import re

MOTIF_JETON = re.compile(r"/r/[^/?#\s\"']+")


def masquer_jetons(texte):
    return MOTIF_JETON.sub("/r/***", texte) if isinstance(texte, str) else texte


class FiltreJetons(logging.Filter):
    def filter(self, record):
        record.msg = masquer_jetons(record.msg)
        if isinstance(record.args, tuple):
            record.args = tuple(masquer_jetons(a) for a in record.args)
        elif isinstance(record.args, dict):
            record.args = {k: masquer_jetons(v) for k, v in record.args.items()}
        return True
