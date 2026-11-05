"""Envoi des invitations, relances et accusés de réception."""
import logging

from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils import timezone

from .models import Envoi, Parametres, Reponse, lien_public

logger = logging.getLogger(__name__)


def _destinataires(reponse):
    adresses = [reponse.epn.email_contact]
    if reponse.email and reponse.email.lower() != reponse.epn.email_contact.lower():
        adresses.append(reponse.email)
    return adresses


def _contexte():
    """Textes paramétrés dans l'interface (F-48) : institution, messages d'invitation et de relance, signature."""
    p = Parametres.charger()
    return {"institution": p.valeur("institution"), "lien_public": lien_public(), "texte_invitation": p.texte_invitation,
            "texte_relance": p.texte_relance, "signature": p.signature, "assistance": p.email_contact}


def _envoyer(reponse, type_envoi, gabarit, sujet, par="", destinataires=None, **extra):
    contexte = _contexte() | {"reponse": reponse, "campagne": reponse.campagne,
                              "date_limite": reponse.date_limite_effective} | extra
    destinataires = destinataires or _destinataires(reponse)
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


def envoyer_acces(reponse):
    """Lien personnel demandé depuis le lien public : toujours envoyé à l'adresse officielle du point focal."""
    ok = _envoyer(reponse, Envoi.Type.ACCES, "acces",
                  f"[{reponse.campagne}] Votre lien d'accès au questionnaire de {reponse.epn.nom}",
                  par="formulaire public", destinataires=[reponse.epn.email_contact])
    if ok and not reponse.date_invitation:
        # Compte comme une invitation : évite un second envoi depuis « Liens et invitations ».
        reponse.date_invitation = timezone.now()
        reponse.save(update_fields=["date_invitation"])
    return ok


def envoyer_nouveau_lien(reponse, par=""):
    """Le lien a été remplacé : le nouveau part à l'adresse officielle du point focal uniquement."""
    return _envoyer(reponse, Envoi.Type.NOUVEAU_LIEN, "nouveau_lien",
                    f"[{reponse.campagne}] Nouveau lien d'accès au questionnaire de {reponse.epn.nom}",
                    par=par, destinataires=[reponse.epn.email_contact])


def envoyer_relance(reponse, par=""):
    if reponse.est_soumise:
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


def envoyer_correction(reponse, par=""):
    """La tutelle renvoie la réponse pour correction, avec ses commentaires (F-30)."""
    q = reponse.campagne.q
    remarques = [{"code": code, "libelle": (q.question(code) or {}).get("libelle", ""), "texte": texte}
                 for code, texte in reponse.commentaires.items() if code != "general"]
    return _envoyer(reponse, Envoi.Type.CORRECTION, "correction",
                    f"[{reponse.campagne}] Corrections demandées – questionnaire de {reponse.epn.nom}", par,
                    remarques=remarques, general=reponse.commentaires.get("general", ""))


def envoyer_validation(reponse, par=""):
    return _envoyer(reponse, Envoi.Type.VALIDATION, "validation",
                    f"[{reponse.campagne}] Réponse validée – {reponse.epn.nom}", par)


def envoyer_lien_mot_de_passe(user, lien, nouveau_compte=False):
    """Lien pour définir (nouveau compte, F-04) ou réinitialiser (F-02) son mot de passe."""
    contexte = _contexte() | {"user": user, "lien": lien, "nouveau_compte": nouveau_compte}
    sujet = "Activez votre compte ENQUÊTE-EPN" if nouveau_compte else "Réinitialisation de votre mot de passe ENQUÊTE-EPN"
    try:
        send_mail(sujet, render_to_string("enquete/emails/mot_de_passe.txt", contexte), settings.DEFAULT_FROM_EMAIL,
                  [user.email])
        return True
    except Exception:
        logger.exception("Échec d'envoi du lien de mot de passe à %s", user.get_username())
        return False
