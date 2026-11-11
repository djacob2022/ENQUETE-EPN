"""Protections transversales : adresse IP réelle, limites anti-abus, connexion, journaux, taille des requêtes."""
import ipaddress
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.signals import user_logged_in, user_login_failed
from django.dispatch import receiver
from django.http import JsonResponse
from django.utils import timezone

# --- Adresse IP du visiteur ----------------------------------------------------------------------

def _ip_valide(texte):
    try:
        return str(ipaddress.ip_address(texte))
    except ValueError:
        return None


def ip_client(request):
    """Adresse du visiteur ; derrière N proxys de confiance, la N-ième en partant de la fin de X-Forwarded-For.

    X-Forwarded-For n'est cru que si la connexion vient d'un réseau privé (le proxy) et si la valeur est une
    adresse IP valide : si NB_PROXYS_DE_CONFIANCE est réglé à tort alors que le site est exposé directement,
    un visiteur ne peut ni choisir son adresse (et contourner les limites) ni provoquer une erreur.
    """
    if request is None:
        return "0.0.0.0"
    directe = _ip_valide(request.META.get("REMOTE_ADDR", "")) or "0.0.0.0"
    n = settings.NB_PROXYS_DE_CONFIANCE
    if not n or not ipaddress.ip_address(directe).is_private:
        return directe
    chaine = [x.strip() for x in request.META.get("HTTP_X_FORWARDED_FOR", "").split(",") if x.strip()]
    if len(chaine) >= n:
        return _ip_valide(chaine[-n]) or directe
    return directe


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
        # Seule la restauration d'une sauvegarde (super-administrateur) accepte un envoi plus gros.
        maximum = (settings.TAILLE_MAX_RESTAURATION if request.path == "/api/gestion/restauration/"
                   else settings.TAILLE_MAX_REQUETE)
        if taille > maximum:
            mo = maximum // (1024 * 1024)
            return JsonResponse({"erreur": f"Envoi trop volumineux : {mo} Mo maximum par envoi."}, status=413)
        return self.get_response(request)


# --- Politique de sécurité du contenu (CSP) -----------------------------------------------------------

CSP = "; ".join([
    "default-src 'self'",
    "script-src 'self'",
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",  # styles calculés par les animations
    "font-src 'self' https://fonts.gstatic.com",
    "img-src 'self' data:",
    "connect-src 'self'",
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
])


class PolitiqueContenu:
    """Le navigateur n'exécute que les scripts du site : une injection de code éventuelle reste sans effet."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        reponse = self.get_response(request)
        reponse.headers.setdefault("Content-Security-Policy", CSP)
        reponse.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        return reponse


# --- Politique de mot de passe (F-01) ------------------------------------------------------------

class ComplexiteMotDePasse:
    """Au moins trois familles de caractères parmi : minuscules, majuscules, chiffres, symboles."""

    def validate(self, password, user=None):
        from django.core.exceptions import ValidationError

        familles = [any(c.islower() for c in password), any(c.isupper() for c in password),
                    any(c.isdigit() for c in password), any(not c.isalnum() for c in password)]
        if sum(familles) < 3:
            raise ValidationError(
                "Le mot de passe doit mêler au moins trois types de caractères : minuscules, majuscules, chiffres, "
                "symboles.", code="mot_de_passe_trop_simple")

    def get_help_text(self):
        return "Au moins trois types de caractères parmi minuscules, majuscules, chiffres et symboles."
