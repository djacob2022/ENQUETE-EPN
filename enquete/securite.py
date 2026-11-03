"""Protections transversales : adresse IP réelle, limites anti-abus, connexion, journaux, taille des requêtes."""
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.signals import user_logged_in, user_login_failed
from django.dispatch import receiver
from django.http import JsonResponse
from django.utils import timezone

# --- Adresse IP du visiteur ----------------------------------------------------------------------

def ip_client(request):
    """Adresse du visiteur ; derrière N proxys de confiance, la N-ième en partant de la fin de X-Forwarded-For."""
    if request is None:
        return "0.0.0.0"
    n = settings.NB_PROXYS_DE_CONFIANCE
    chaine = [x.strip() for x in request.META.get("HTTP_X_FORWARDED_FOR", "").split(",") if x.strip()]
    if n and len(chaine) >= n:
        return chaine[-n]
    return request.META.get("REMOTE_ADDR", "0.0.0.0")


def trop_de_demandes_acces(request, limite=10, fenetre=timedelta(minutes=10)):
    """Au plus `limite` demandes de lien par adresse IP sur la fenêtre glissante.

    Chaque demande est une ligne en base : le compte est partagé entre les processus du serveur, survit aux
    redémarrages, et deux demandes simultanées ne peuvent pas « perdre » une incrémentation.
    """
    from .models import DemandeAcces

    debut = timezone.now() - fenetre
    DemandeAcces.objects.filter(date__lt=debut).delete()
    ip = ip_client(request)
    DemandeAcces.objects.create(ip=ip)
    return DemandeAcces.objects.filter(ip=ip, date__gte=debut).count() > limite


# --- Connexion : blocage temporaire après des échecs répétés ---------------------------------------
# Couvre l'API (/api/auth/connexion/) comme /django-admin/ : les deux passent par authenticate().

ECHECS_MAX_PAR_COMPTE = 5
ECHECS_MAX_PAR_IP = 20
DUREE_BLOCAGE = timedelta(minutes=15)


def connexion_bloquee(identifiant, request):
    from .models import EchecConnexion

    debut = timezone.now() - DUREE_BLOCAGE
    EchecConnexion.objects.filter(date__lt=debut).delete()
    recents = EchecConnexion.objects.filter(date__gte=debut)
    return (recents.filter(identifiant__iexact=identifiant or "").count() >= ECHECS_MAX_PAR_COMPTE
            or recents.filter(ip=ip_client(request)).count() >= ECHECS_MAX_PAR_IP)


class AuthentificationProtegee(ModelBackend):
    """Refuse toute tentative (même avec le bon mot de passe) tant que le compte ou l'adresse est bloqué."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        if connexion_bloquee(username, request):
            return None
        return super().authenticate(request, username=username, password=password, **kwargs)


@receiver(user_login_failed)
def noter_echec(sender, credentials, request=None, **kwargs):
    from .models import EchecConnexion

    EchecConnexion.objects.create(identifiant=(credentials.get("username") or "")[:150], ip=ip_client(request))


@receiver(user_logged_in)
def effacer_echecs(sender, request, user, **kwargs):
    from .models import EchecConnexion

    EchecConnexion.objects.filter(identifiant__iexact=user.get_username()).delete()


# --- Taille des requêtes : refus avant la lecture du corps -------------------------------------------

class LimiteTailleRequete:
    """Refuse d'emblée (413) un corps plus gros que TAILLE_MAX_REQUETE, sans le lire ni l'écrire sur le disque."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            taille = int(request.META.get("CONTENT_LENGTH") or 0)
        except ValueError:
            taille = 0
        if taille > settings.TAILLE_MAX_REQUETE:
            mo = settings.TAILLE_MAX_REQUETE // (1024 * 1024)
            return JsonResponse({"erreur": f"Envoi trop volumineux : {mo} Mo maximum par envoi."}, status=413)
        return self.get_response(request)
