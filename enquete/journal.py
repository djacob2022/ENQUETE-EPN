"""Écriture dans le journal d'audit (F-46). Toujours appelé après une action réussie."""
import logging

from .securite import ip_client

journal_technique = logging.getLogger("enquete.audit")


def auteur_de(request):
    user = getattr(request, "user", None)
    if user is not None and user.is_authenticated:
        return user.get_username()
    return ""


def tracer(request, action, objet="", auteur=None, **detail):
    """Ajoute une ligne au journal. Une panne d'écriture ne doit jamais bloquer l'action elle-même."""
    from .models import Journal

    try:
        Journal.objects.create(auteur=(auteur if auteur is not None else auteur_de(request))[:150], action=action,
                               objet=str(objet)[:255], detail=detail, ip=ip_client(request) if request else None)
    except Exception:  # pragma: no cover - la base est indisponible : on garde au moins une trace technique
        journal_technique.exception("Écriture impossible dans le journal d'audit : %s %s", action, objet)


LIBELLES = {
    "rapport_annuel": "Rapport annuel", "synthese_ia": "Synthèse IA", "assistant_ia": "Question à l'assistant IA",
    "rapport_auto": "Rapport annuel envoyé automatiquement",
    "connexion": "Connexion", "connexion_echec": "Échec de connexion", "deconnexion": "Déconnexion",
    "mot_de_passe_demande": "Mot de passe oublié", "mot_de_passe_change": "Mot de passe défini",
    "export": "Export", "soumission": "Réponse envoyée par l'EPN", "revue": "Prise en revue", "validation": "Validation",
    "correction": "Renvoi pour correction", "rouverture": "Réouverture", "prolongation": "Délai prolongé",
    "relance": "Relance", "relance_auto": "Relance automatique", "invitation": "Invitation",
    "nouveau_lien": "Lien remplacé", "campagne": "Campagne", "questionnaire": "Questionnaire modifié",
    "epn": "Fiche EPN", "import_epn": "Import du répertoire", "reference": "Liste de référence",
    "compte": "Compte", "deux_facteurs": "Double authentification", "sauvegarde": "Sauvegarde",
    "restauration": "Restauration", "import_excel": "Import Excel", "parametres": "Paramètres", "preremplissage": "Pré-remplissage",
}
