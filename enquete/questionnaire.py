"""Définition du questionnaire adressé aux Établissements Publics Nationaux.

Chaque module regroupe des questions identifiées par un code stable (A01, D03…).
Ces codes sont les noms de colonnes de l'export Excel et les clés du champ JSON
`Reponse.donnees` : ne pas les renommer d'une campagne à l'autre.

Types disponibles : texte, texte_long, entier, montant, pourcentage, choix, choix_multiple, oui_non, url, fichier.
Pour « fichier », la valeur stockée dans `donnees` est le nom du fichier déposé ; le fichier lui-même est un `PieceJointe`.
"""

OUI_NON = [("oui", "Oui"), ("non", "Non")]

MODULES = [
    {
        "code": "A",
        "titre": "Identification de l'établissement",
        "intro": "Informations générales sur l'EPN.",
        "questions": [
            {"code": "A01", "libelle": "Dénomination complète", "type": "texte"},
            {"code": "A02", "libelle": "Sigle", "type": "texte", "obligatoire": False},
            {"code": "A03", "libelle": "Catégorie", "type": "choix",
             "choix": [("EPA", "Établissement public à caractère administratif (EPA)"),
                       ("EPIC", "Établissement public à caractère industriel et commercial (EPIC)"),
                       ("AUTRE", "Autre catégorie")]},
            {"code": "A04", "libelle": "Référence du texte de création (décret, loi)", "type": "texte"},
            {"code": "A05", "libelle": "Année de création", "type": "entier", "min": 1900, "max": 2100, "annee": True},
            {"code": "A06", "libelle": "Ministère de tutelle technique", "type": "texte"},
            {"code": "A07", "libelle": "Ville du siège", "type": "texte"},
            {"code": "A08", "libelle": "Site web", "type": "url", "obligatoire": False},
        ],
    },
    {
        "code": "B",
        "titre": "Gouvernance",
        "intro": "Organes de gestion et outils de pilotage au cours de l'exercice.",
        "questions": [
            {"code": "B01", "libelle": "L'établissement dispose-t-il d'un conseil de gestion (ou d'administration) ?", "type": "oui_non"},
            {"code": "B02", "libelle": "Nombre de sessions du conseil tenues pendant l'exercice", "type": "entier", "min": 0, "max": 50},
            {"code": "B03", "libelle": "Un contrat de performance est-il signé avec l'État ?", "type": "oui_non"},
            {"code": "B04", "libelle": "Un plan stratégique est-il en cours d'exécution ?", "type": "oui_non"},
            {"code": "B05", "libelle": "L'établissement dispose-t-il d'une fonction d'audit interne ?", "type": "oui_non"},
        ],
    },
    {
        "code": "C",
        "titre": "Missions et activités",
        "intro": "",
        "questions": [
            {"code": "C01", "libelle": "Principales missions statutaires", "type": "texte_long"},
            {"code": "C02", "libelle": "Couverture géographique des activités", "type": "choix",
             "choix": [("nationale", "Nationale"), ("regionale", "Régionale"), ("locale", "Locale")]},
            {"code": "C03", "libelle": "Nombre de bénéficiaires ou d'usagers servis pendant l'exercice", "type": "entier",
             "min": 0, "obligatoire": False},
        ],
    },
    {
        "code": "D",
        "titre": "Ressources humaines",
        "intro": "Effectifs au 31 décembre de l'exercice de référence, tous statuts confondus.",
        "questions": [
            {"code": "D01", "libelle": "Effectif total", "type": "entier", "min": 0, "max": 100000, "unite": "agents"},
            {"code": "D02", "libelle": "Dont femmes", "type": "entier", "min": 0, "unite": "agents"},
            {"code": "D03", "libelle": "Dont hommes", "type": "entier", "min": 0, "unite": "agents"},
            {"code": "D04", "libelle": "Dont fonctionnaires", "type": "entier", "min": 0, "unite": "agents"},
            {"code": "D05", "libelle": "Dont contractuels", "type": "entier", "min": 0, "unite": "agents"},
            {"code": "D06", "libelle": "Recrutements pendant l'exercice", "type": "entier", "min": 0, "unite": "agents"},
            {"code": "D07", "libelle": "Départs pendant l'exercice (retraite, démission, fin de contrat…)", "type": "entier", "min": 0, "unite": "agents"},
            {"code": "D08", "libelle": "Masse salariale annuelle", "type": "montant"},
        ],
    },
    {
        "code": "E",
        "titre": "Finances",
        "intro": "Montants de l'exercice de référence, en monnaie locale.",
        "questions": [
            {"code": "E01", "libelle": "Budget prévu (crédits ouverts)", "type": "montant"},
            {"code": "E02", "libelle": "Budget exécuté", "type": "montant"},
            {"code": "E03", "libelle": "Subvention reçue de l'État", "type": "montant"},
            {"code": "E04", "libelle": "Ressources propres encaissées", "type": "montant"},
            {"code": "E05", "libelle": "Dépenses de personnel", "type": "montant"},
            {"code": "E06", "libelle": "Dépenses de fonctionnement", "type": "montant"},
            {"code": "E07", "libelle": "Dépenses d'investissement", "type": "montant"},
            {"code": "E08", "libelle": "Dettes et arriérés au 31 décembre", "type": "montant", "obligatoire": False},
        ],
    },
    {
        "code": "F",
        "titre": "Patrimoine et numérique",
        "intro": "",
        "questions": [
            {"code": "F01", "libelle": "Nombre de bâtiments occupés", "type": "entier", "min": 0},
            {"code": "F02", "libelle": "Nombre de véhicules en service", "type": "entier", "min": 0},
            {"code": "F03", "libelle": "Nombre d'ordinateurs en service", "type": "entier", "min": 0},
            {"code": "F04", "libelle": "L'établissement dispose-t-il d'une connexion Internet permanente ?", "type": "oui_non"},
            {"code": "F05", "libelle": "Logiciels de gestion utilisés", "type": "choix_multiple", "obligatoire": False,
             "choix": [("comptabilite", "Comptabilité"), ("paie", "Paie / RH"), ("courrier", "Gestion du courrier"),
                       ("metier", "Logiciel métier"), ("aucun", "Aucun")]},
        ],
    },
    {
        "code": "G",
        "titre": "Performance",
        "intro": "Indicateurs du contrat de performance ou, à défaut, du plan d'actions annuel.",
        "questions": [
            {"code": "G01", "libelle": "Nombre d'indicateurs suivis", "type": "entier", "min": 0},
            {"code": "G02", "libelle": "Nombre d'indicateurs dont la cible est atteinte", "type": "entier", "min": 0},
            {"code": "G03", "libelle": "Taux d'exécution du plan d'actions", "type": "pourcentage"},
        ],
    },
    {
        "code": "H",
        "titre": "Difficultés et besoins",
        "intro": "",
        "questions": [
            {"code": "H01", "libelle": "Principales difficultés rencontrées", "type": "choix_multiple",
             "choix": [("financieres", "Financières"), ("humaines", "Ressources humaines"), ("materielles", "Matérielles"),
                       ("juridiques", "Juridiques ou réglementaires"), ("numeriques", "Numériques"), ("autres", "Autres")]},
            {"code": "H02", "libelle": "Besoins prioritaires pour l'exercice suivant", "type": "texte_long"},
            {"code": "H03", "libelle": "Observations complémentaires", "type": "texte_long", "obligatoire": False},
        ],
    },
    {
        "code": "J",
        "titre": "Pièces justificatives",
        "intro": "Formats acceptés : PDF, Word, Excel, JPG ou PNG, 10 Mo maximum par fichier.",
        "questions": [
            {"code": "J01", "libelle": "États financiers de l'exercice", "type": "fichier"},
            {"code": "J02", "libelle": "Rapport d'activités de l'exercice", "type": "fichier"},
            {"code": "J03", "libelle": "Organigramme", "type": "fichier", "obligatoire": False},
            {"code": "J04", "libelle": "Procès-verbaux du conseil de gestion", "type": "fichier", "obligatoire": False},
            {"code": "J05", "libelle": "Autre document utile", "type": "fichier", "obligatoire": False},
        ],
    },
]


def _verifier_somme(total, parties, message):
    def regle(d):
        if d.get(total) is None or any(d.get(p) is None for p in parties):
            return None
        if sum(d[p] for p in parties) != d[total]:
            return message.format(somme=sum(d[p] for p in parties), total=d[total])
        return None
    return regle


def _inferieur_ou_egal(petit, grand, message):
    def regle(d):
        if d.get(petit) is None or d.get(grand) is None:
            return None
        return message if d[petit] > d[grand] else None
    return regle


# Règles de cohérence : (codes des champs concernés, fonction(donnees) -> message ou None).
REGLES_COHERENCE = {
    "D": [
        (("D02", "D03"), _verifier_somme("D01", ("D02", "D03"),
            "Femmes + hommes = {somme}, différent de l'effectif total ({total}).")),
        (("D04", "D05"), _verifier_somme("D01", ("D04", "D05"),
            "Fonctionnaires + contractuels = {somme}, différent de l'effectif total ({total}).")),
    ],
    "G": [
        (("G02",), _inferieur_ou_egal("G02", "G01",
            "Le nombre d'indicateurs atteints dépasse le nombre d'indicateurs suivis.")),
    ],
}

TYPES_NUMERIQUES = {"entier", "montant", "pourcentage"}


def toutes_les_questions():
    for module in MODULES:
        for q in module["questions"]:
            yield module, q


def question(code):
    for _, q in toutes_les_questions():
        if q["code"] == code:
            return q
    raise KeyError(code)


def module_index(code_module):
    for i, m in enumerate(MODULES):
        if m["code"] == code_module:
            return i
    raise KeyError(code_module)


def libelle_reponse(q, valeur):
    """Valeur lisible pour l'affichage et l'export Excel."""
    if valeur in (None, "", []):
        return ""
    if q["type"] == "oui_non":
        return dict(OUI_NON).get(valeur, valeur)
    if q["type"] == "choix":
        return dict(q["choix"]).get(valeur, valeur)
    if q["type"] == "choix_multiple":
        libelles = dict(q["choix"])
        return ", ".join(libelles.get(v, v) for v in valeur)
    return valeur


def affichage(q, valeur):
    """Valeur mise en forme pour les récapitulatifs à l'écran (milliers séparés, pourcentages…)."""
    if valeur in (None, "", []):
        return ""
    if q["type"] in ("entier", "montant") and not q.get("annee"):
        texte = f"{valeur:,.2f}".rstrip("0").rstrip(".") if isinstance(valeur, float) else f"{valeur:,}"
        return texte.replace(",", "\u202f").replace(".", ",")
    if q["type"] == "pourcentage":
        return f"{valeur} %".replace(".", ",")
    return str(libelle_reponse(q, valeur))
