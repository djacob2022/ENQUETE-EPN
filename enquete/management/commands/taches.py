"""Tâches planifiées (F-19) : relances automatiques J-7, J-2, J+1… selon le réglage de chaque campagne, et envoi
automatique du rapport annuel aux administrateurs RAPPORT_AUTO_JOURS jours après la clôture de chaque campagne.

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


def destinataires_rapport():
    from django.contrib.auth import get_user_model

    from enquete.models import permissions_de

    return sorted({u.email for u in get_user_model().objects.filter(is_active=True, is_staff=True).exclude(email="")
                   if u.is_superuser or "gerer_campagnes" in permissions_de(u)})


def rapports_automatiques(aujourd_hui=None):
    """Rapport annuel de chaque campagne close depuis RAPPORT_AUTO_JOURS jours, envoyé une seule fois aux
    administrateurs (avec la synthèse IA si l'assistant est configuré)."""
    from datetime import timedelta

    from django.conf import settings
    from django.core.mail import EmailMessage

    from enquete import assistant, rapport
    from enquete.models import Journal, SyntheseIA

    if not str(settings.RAPPORT_AUTO_JOURS).strip():
        return 0
    aujourd_hui = aujourd_hui or timezone.localdate()
    limite = aujourd_hui - timedelta(days=int(settings.RAPPORT_AUTO_JOURS))
    envoyes = 0
    # Fenêtre de 60 jours : à la mise en service, les campagnes closes depuis longtemps ne déclenchent pas d'envoi.
    for c in Campagne.objects.filter(date_cloture__lte=limite, date_cloture__gt=limite - timedelta(days=60)):
        if Journal.objects.filter(action="rapport_auto", detail__campagne=c.pk).exists():
            continue
        destinataires = destinataires_rapport()
        if not destinataires:
            continue
        precedente = Campagne.objects.filter(exercice__lt=c.exercice).order_by("-exercice").first()
        d = rapport.collecter(c, c.reponses.select_related("epn"), "validees", precedente,
                              precedente.reponses.select_related("epn") if precedente else None)
        s = SyntheseIA.objects.filter(campagne=c, perimetre="", base="validees").first()
        if s is None and assistant.disponible() and d["reponses"]:
            try:
                contenu, modele = assistant.synthese_rapport(assistant.contexte(d, nominatif=True))
                s = SyntheseIA.objects.create(campagne=c, perimetre="", base="validees", contenu=contenu, modele=modele,
                                              auteur="système", nombre_reponses=len(d["reponses"]))
            except Exception:  # le rapport part quand même, sans synthèse IA
                logger.exception("Synthèse IA impossible pour le rapport automatique de %s", c)
        message = EmailMessage(
            f"[ENQUÊTE-EPN] Rapport annuel {c.exercice} : {c.nom}",
            f"Bonjour,\n\nLa campagne « {c.nom} » est close depuis le {c.date_cloture:%d/%m/%Y}. Vous trouverez ci-joint "
            f"le rapport annuel généré automatiquement ({d['participation']['soumis']} réponse(s) transmise(s) sur "
            f"{d['participation']['invites']}, statistiques sur les {len(d['reponses'])} réponse(s) validée(s)).\n\n"
            f"Le rapport peut être régénéré à tout moment depuis la page Statistiques de l'application, par exemple après "
            f"de nouvelles validations.\n\nENQUÊTE-EPN",
            settings.DEFAULT_FROM_EMAIL, destinataires)
        message.attach(rapport.nom_fichier(c), rapport.generer(d, s.contenu if s else None), "application/pdf")
        try:
            message.send()
        except Exception:
            logger.exception("Envoi du rapport annuel automatique impossible pour %s", c)
            continue
        envoyes += 1
        tracer(None, "rapport_auto", f"Rapport annuel {c}", auteur="système", campagne=c.pk,
               destinataires=len(destinataires), ia=bool(s))
    return envoyes


class Command(BaseCommand):
    help = "Envoie les relances automatiques prévues aujourd'hui et les rapports annuels des campagnes closes."

    def add_arguments(self, parser):
        parser.add_argument("--boucle", action="store_true", help="Recommence toutes les heures.")

    def handle(self, *args, boucle=False, **options):
        while True:
            try:
                n = relances_du_jour()
                r = rapports_automatiques()
                self.stdout.write(f"{timezone.now():%Y-%m-%d %H:%M} · {n} relance(s) automatique(s) envoyée(s), "
                                  f"{r} rapport(s) annuel(s) envoyé(s).")
            except Exception:
                logger.exception("Échec des relances automatiques")
                if not boucle:
                    raise
            if not boucle:
                return
            time.sleep(3600)
