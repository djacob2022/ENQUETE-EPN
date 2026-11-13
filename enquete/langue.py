"""Version anglaise du parcours de l'établissement (F-16).

L'équipe d'enquête travaille en français ; l'établissement répondant choisit le français ou l'anglais. La langue est
transmise par l'en-tête « X-Langue: en » (ou le paramètre « ?langue=en » pour les téléchargements) sur les adresses
publiques du questionnaire. Pendant la requête, Django est alors en anglais : messages de validation intégrés,
questionnaire traduit (Campagne.q) et messages propres à l'application traduits ci-dessous.
"""
import re

from django.utils import translation

LANGUES = ("fr", "en")
CHEMINS_PUBLICS = ("/api/r/", "/api/formulaire/", "/api/questionnaire/", "/api/config/")


def anglais():
    return (translation.get_language() or "").startswith("en")


def langue_demandee(request):
    langue = (request.headers.get("X-Langue") or request.GET.get("langue") or "").lower()[:2]
    return langue if langue in LANGUES else None


class LangueRepondant:
    """Active l'anglais pour les requêtes publiques du répondant qui le demandent."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        langue = langue_demandee(request) if request.path.startswith(CHEMINS_PUBLICS) else None
        if langue != "en":
            return self.get_response(request)
        with translation.override("en"):
            return self.get_response(request)


MESSAGES = {
    "Rubrique inconnue.": "Unknown section.",
    "Ce questionnaire a déjà été envoyé.": "This questionnaire has already been submitted.",
    "La campagne n'est pas ouverte à la saisie.": "The survey is not open for input.",
    "Renseignez d'abord vos coordonnées.": "Please enter your contact details first.",
    "Cette question n'accepte pas de fichier.": "This question does not accept files.",
    "Aucun fichier pour cette question.": "No file for this question.",
    "Cochez la case de certification pour envoyer.": "Tick the certification box to submit.",
    "Aucune réponse de votre établissement à une campagne précédente.":
        "No answer from your institution to a previous survey.",
    "Campagne introuvable.": "Survey not found.",
    "Aucune campagne.": "No survey.",
    "Le fichier est vide.": "The file is empty.",
    "Le contenu du fichier ne correspond pas à son extension.": "The file content does not match its extension.",
    "Numéro de téléphone incomplet (8 chiffres au moins).": "Incomplete phone number (at least 8 digits).",
    "Tableau illisible.": "Unreadable table.",
    "Choisissez le fichier Excel (.xlsx) téléchargé depuis votre questionnaire.":
        "Choose the Excel file (.xlsx) downloaded from your questionnaire.",
    "Fichier trop volumineux (5 Mo maximum).": "File too large (5 MB maximum).",
    "Ce fichier n'est pas le modèle du questionnaire : téléchargez-le à nouveau depuis votre lien.":
        "This file is not the questionnaire template: download it again from your link.",
    "Aucune réponse trouvée dans la colonne « Votre réponse ».": "No answers found in the “Your answer” column.",
    "Le questionnaire n'est pas ouvert en ce moment.": "The questionnaire is not open at the moment.",
    "Choisissez votre établissement dans la liste.": "Choose your institution from the list.",
    "Aucun fichier reçu.": "No file received.",
    "Lien invalide ou expiré.": "Invalid or expired link.",
    "Requête invalide.": "Invalid request.",
}

MOTIFS = [
    (re.compile(r"^Rubriques à compléter avant l'envoi : (.*)\.$"), "Sections to complete before submitting: {0}."),
    (re.compile(r"^Format non accepté\. Formats autorisés : .*\.$"),
     "Format not accepted. Allowed formats: PDF, Word, Excel, JPG or PNG."),
    (re.compile(r"^Fichier trop volumineux \((.*)\)\. Maximum : (.*)\.$"), "File too large ({0}). Maximum: {1}."),
    (re.compile(r"^« (.*) » doit être un nombre \(ligne (\d+)\)\.$"), "“{0}” must be a number (row {1})."),
    (re.compile(r"^(\d+) lignes au maximum\.$"), "{0} rows maximum."),
    (re.compile(r"^Trop de demandes depuis cette connexion.*"),
     "Too many requests from this connection. To protect institutions, sending is temporarily limited: try again "
     "later."),
    (re.compile(r"^Le lien n'a pas pu être envoyé.*"),
     "The link could not be sent: the email service is temporarily unavailable. Try again in a few minutes."),
]


def tr(message):
    """Message en anglais si le répondant a choisi l'anglais (sinon inchangé)."""
    if not anglais() or not isinstance(message, str):
        return message
    if message in MESSAGES:
        return MESSAGES[message]
    for motif, gabarit in MOTIFS:
        m = motif.match(message)
        if m:
            return gabarit.format(*m.groups())
    return message


def tr_erreurs(erreurs):
    """Traduit un dictionnaire {champ: [messages]} ou une liste de messages."""
    if not anglais():
        return erreurs
    if isinstance(erreurs, dict):
        return {k: tr_erreurs(v) for k, v in erreurs.items()}
    if isinstance(erreurs, (list, tuple)):
        return [tr_erreurs(v) for v in erreurs]
    return tr(erreurs)
