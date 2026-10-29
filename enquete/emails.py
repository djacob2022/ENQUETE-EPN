"""Envoi des invitations, relances et accusés de réception."""
import logging

from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils import timezone

from .models import Envoi, Reponse

logger = logging.getLogger(__name__)


def _destinataires(reponse):
    adresses = [reponse.epn.email_contact]
    if reponse.email and reponse.email.lower() != reponse.epn.email_contact.lower():
        adresses.append(reponse.email)
    return adresses


def _envoyer(reponse, type_envoi, gabarit, sujet, par=""):
    contexte = {"reponse": reponse, "campagne": reponse.campagne, "institution": settings.NOM_INSTITUTION}
    destinataires = _destinataires(reponse)
    envoi = Envoi(reponse=reponse, type=type_envoi, destinataires=", ".join(destinataires), par=par)
    try:
        send_mail(
            sujet,
            render_to_string(f"enquete/emails/{gabarit}.txt", contexte),
            settings.DEFAULT_FROM_EMAIL,
            destinataires,
        )
    except Exception as exc:  # SMTP indisponible, adresse refusée…
        logger.exception("Échec d'envoi %s pour %s", type_envoi, reponse)
        envoi.succes = False
        envoi.erreur = str(exc)[:1000]
    envoi.save()
    return envoi.succes


def envoyer_invitation(reponse, par=""):
    ok = _envoyer(reponse, Envoi.Type.INVITATION, "invitation",
                  f"[{reponse.campagne}] Questionnaire à renseigner pour {reponse.epn.nom}", par)
    if ok:
        reponse.date_invitation = timezone.now()
        reponse.save(update_fields=["date_invitation"])
    return ok


def envoyer_relance(reponse, par=""):
    if reponse.statut == Reponse.Statut.SOUMIS:
        return False
    ok = _envoyer(reponse, Envoi.Type.RELANCE, "relance",
                  f"Rappel – [{reponse.campagne}] questionnaire de {reponse.epn.nom} à compléter", par)
    if ok:
        reponse.date_derniere_relance = timezone.now()
        reponse.nombre_relances += 1
        reponse.save(update_fields=["date_derniere_relance", "nombre_relances"])
    return ok


def envoyer_accuse(reponse):
    return _envoyer(reponse, Envoi.Type.ACCUSE, "accuse",
                    f"Accusé de réception – [{reponse.campagne}] {reponse.epn.nom}")
