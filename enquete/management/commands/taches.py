"""Tâches planifiées (F-19) : relances automatiques J-7, J-2, J+1… selon le réglage de chaque campagne.

    python manage.py taches            # un passage (à lancer par cron)
    python manage.py taches --boucle   # passage toutes les heures (service « taches » de docker-compose)

Chaque EPN reçoit au plus une relance automatique par jour prévu, même si la commande passe plusieurs fois.
"""
import logging
import time

from django.core.management.base import BaseCommand
from django.utils import timezone

from enquete.emails import envoyer_relance
from enquete.journal import tracer
from enquete.models import Campagne, Envoi, Reponse

PAR = "relance automatique"
logger = logging.getLogger(__name__)


def relances_du_jour(aujourd_hui=None):
    aujourd_hui = aujourd_hui or timezone.localdate()
    envoyees = 0
    for c in Campagne.objects.filter(active=True):
        for r in c.reponses.exclude(statut__in=Reponse.ENVOYES).filter(date_invitation__isnull=False).select_related(
                "epn", "campagne"):
            # Le décompte suit le délai propre à l'EPN (prolongation comprise).
            if (aujourd_hui - r.date_limite_effective).days not in c.jours_relance:
                continue
            deja = r.envois.filter(type=Envoi.Type.RELANCE, par=PAR, date__date=aujourd_hui).exists()
            if not deja and envoyer_relance(r, par=PAR):
                envoyees += 1
                tracer(None, "relance_auto", r.epn.nom, auteur="système", reponse=r.pk, epn=r.epn.nom,
                       tutelle=r.epn.tutelle, campagne=c.pk)
    return envoyees


class Command(BaseCommand):
    help = "Envoie les relances automatiques prévues aujourd'hui."

    def add_arguments(self, parser):
        parser.add_argument("--boucle", action="store_true", help="Recommence toutes les heures.")

    def handle(self, *args, boucle=False, **options):
        while True:
            try:
                n = relances_du_jour()
                self.stdout.write(f"{timezone.now():%Y-%m-%d %H:%M} · {n} relance(s) automatique(s) envoyée(s).")
            except Exception:
                logger.exception("Échec des relances automatiques")
                if not boucle:
                    raise
            if not boucle:
                return
            time.sleep(3600)
