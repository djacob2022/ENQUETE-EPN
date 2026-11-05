"""Questionnaire adressé aux Établissements Publics Nationaux (section 4 du cahier des charges).

Le questionnaire est **propre à chaque campagne** (champ JSON `Campagne.questionnaire`) : l'administrateur le
modifie dans l'éditeur sans développement (F-10), et une nouvelle campagne reprend celui de la précédente (F-14).
`DEFINITION_PAR_DEFAUT` ci-dessous n'est que le point de départ de la toute première campagne.

Chaque question porte un code stable (A01, D03…) : c'est la clé du champ JSON `Reponse.donnees` et le nom de
colonne de l'export Excel. Un code n'est jamais réattribué à une autre question.

Types (F-11) : texte, texte_long, entier, montant, pourcentage, date, choix, choix_multiple, oui_non, echelle,
tableau (lignes répétables), url, fichier.
Condition d'affichage (F-13) : {"si": {"question": "B03", "valeurs": ["oui"]}} — la question n'est posée (et
obligatoire) que si la réponse à B03 est « oui ».
Règles de cohérence (F-12) : {"type": "somme", "total": "D01", "parties": ["D02", "D03"]} ou
{"type": "inferieur", "petit": "G02", "grand": "G01"}.
"""
import copy

OUI_NON = [["oui", "Oui"], ["non", "Non"]]

TYPES = {
    "texte": "Texte court", "texte_long": "Texte long", "entier": "Nombre entier", "montant": "Montant",
    "pourcentage": "Pourcentage", "date": "Date", "choix": "Choix unique", "choix_multiple": "Choix multiple",
    "oui_non": "Oui / non", "echelle": "Échelle", "tableau": "Tableau à lignes répétables", "url": "Adresse web",
    "fichier": "Fichier joint",
}
TYPES_NUMERIQUES = {"entier", "montant", "pourcentage"}
TYPES_A_CHOIX = {"choix", "choix_multiple"}

MODULES_PAR_DEFAUT = [
    {
        "code": "A", "titre": "Identification de l'établissement", "intro": "Informations générales sur l'EPN.",
        "questions": [
            {"code": "A01", "libelle": "Dénomination complète", "type": "texte"},
            {"code": "A02", "libelle": "Sigle", "type": "texte", "obligatoire": False},
            {"code": "A03", "libelle": "Catégorie", "type": "choix",
             "choix": [["EPA", "Établissement public à caractère administratif (EPA)"],
                       ["EPIC", "Établissement public à caractère industriel et commercial (EPIC)"],
                       ["AUTRE", "Autre catégorie"]]},
            {"code": "A04", "libelle": "Référence du texte de création (décret, loi)", "type": "texte"},
            {"code": "A05", "libelle": "Date de création", "type": "date"},
            {"code": "A06", "libelle": "Ministère de tutelle technique", "type": "texte"},
            {"code": "A07", "libelle": "Ville du siège", "type": "texte"},
            {"code": "A08", "libelle": "Région du siège", "type": "texte"},
            {"code": "A09", "libelle": "Téléphone du standard", "type": "texte"},
            {"code": "A10", "libelle": "Adresse e-mail générale", "type": "texte", "obligatoire": False},
            {"code": "A11", "libelle": "Site web", "type": "url", "obligatoire": False},
        ],
    },
    {
        "code": "B", "titre": "Gouvernance", "intro": "Organes de gestion et outils de pilotage au cours de l'exercice.",
        "questions": [
            {"code": "B01", "libelle": "Nom du directeur général", "type": "texte"},
            {"code": "B02", "libelle": "Date de nomination du directeur général", "type": "date"},
            {"code": "B03", "libelle": "L'établissement dispose-t-il d'un conseil de gestion (ou d'administration) ?",
             "type": "oui_non"},
            {"code": "B04", "libelle": "Nombre de membres du conseil", "type": "entier", "min": 1, "max": 100,
             "si": {"question": "B03", "valeurs": ["oui"]}},
            {"code": "B05", "libelle": "Nombre de sessions du conseil tenues pendant l'exercice", "type": "entier",
             "min": 0, "max": 50, "si": {"question": "B03", "valeurs": ["oui"]}},
            {"code": "B06", "libelle": "Un contrat de performance est-il signé avec l'État ?", "type": "oui_non"},
            {"code": "B07", "libelle": "L'établissement dispose-t-il d'une fonction d'audit interne ?", "type": "oui_non"},
            {"code": "B08", "libelle": "Un plan stratégique est-il en cours d'exécution ?", "type": "oui_non"},
        ],
    },
    {
        "code": "C", "titre": "Missions et activités", "intro": "",
        "questions": [
            {"code": "C01", "libelle": "Missions statutaires", "type": "texte_long"},
            {"code": "C02", "libelle": "Principales prestations délivrées", "type": "texte_long"},
            {"code": "C03", "libelle": "Bénéficiaires des prestations", "type": "choix_multiple",
             "choix": [["public", "Grand public"], ["entreprises", "Entreprises"], ["administrations", "Administrations"],
                       ["eleves", "Élèves et étudiants"], ["patients", "Patients"], ["producteurs", "Producteurs agricoles"],
                       ["autres", "Autres"]]},
            {"code": "C04", "libelle": "Couverture géographique des activités", "type": "choix",
             "choix": [["nationale", "Nationale"], ["regionale", "Régionale"], ["locale", "Locale"]]},
            {"code": "C05", "libelle": "Nombre de bénéficiaires ou d'usagers servis pendant l'exercice", "type": "entier",
             "min": 0, "obligatoire": False},
        ],
    },
    {
        "code": "D", "titre": "Ressources humaines",
        "intro": "Effectifs au 31 décembre de l'exercice de référence, tous statuts confondus.",
        "questions": [
            {"code": "D01", "libelle": "Effectif total", "type": "entier", "min": 0, "max": 100000, "unite": "agents"},
            {"code": "D02", "libelle": "Dont femmes", "type": "entier", "min": 0, "unite": "agents"},
            {"code": "D03", "libelle": "Dont hommes", "type": "entier", "min": 0, "unite": "agents"},
            {"code": "D04", "libelle": "Dont fonctionnaires", "type": "entier", "min": 0, "unite": "agents"},
            {"code": "D05", "libelle": "Dont contractuels", "type": "entier", "min": 0, "unite": "agents"},
            {"code": "D09", "libelle": "Dont cadres", "type": "entier", "min": 0, "unite": "agents"},
            {"code": "D10", "libelle": "Dont agents de maîtrise et d'exécution", "type": "entier", "min": 0, "unite": "agents"},
            {"code": "D11", "libelle": "Agents de moins de 35 ans", "type": "entier", "min": 0, "unite": "agents"},
            {"code": "D12", "libelle": "Agents de 35 à 50 ans", "type": "entier", "min": 0, "unite": "agents"},
            {"code": "D13", "libelle": "Agents de plus de 50 ans", "type": "entier", "min": 0, "unite": "agents"},
            {"code": "D06", "libelle": "Recrutements pendant l'exercice", "type": "entier", "min": 0, "unite": "agents"},
            {"code": "D07", "libelle": "Départs pendant l'exercice (retraite, démission, fin de contrat…)", "type": "entier",
             "min": 0, "unite": "agents"},
            {"code": "D08", "libelle": "Masse salariale annuelle", "type": "montant"},
        ],
    },
    {
        "code": "E", "titre": "Finances", "intro": "Montants de l'exercice de référence, en monnaie locale.",
        "questions": [
            {"code": "E01", "libelle": "Budget prévu (crédits ouverts)", "type": "montant"},
            {"code": "E02", "libelle": "Budget exécuté", "type": "montant"},
            {"code": "E03", "libelle": "Subvention reçue de l'État", "type": "montant"},
            {"code": "E04", "libelle": "Ressources propres encaissées", "type": "montant"},
            {"code": "E05", "libelle": "Dépenses de personnel", "type": "montant"},
            {"code": "E06", "libelle": "Dépenses de fonctionnement", "type": "montant"},
            {"code": "E07", "libelle": "Dépenses d'investissement", "type": "montant"},
            {"code": "E08", "libelle": "Dettes au 31 décembre", "type": "montant", "obligatoire": False},
            {"code": "E09", "libelle": "Arriérés de paiement au 31 décembre", "type": "montant", "obligatoire": False},
        ],
    },
    {
        "code": "F", "titre": "Patrimoine et moyens", "intro": "",
        "questions": [
            {"code": "F01", "libelle": "Nombre de bâtiments occupés", "type": "entier", "min": 0},
            {"code": "F02", "libelle": "Nombre de véhicules en service", "type": "entier", "min": 0},
            {"code": "F03", "libelle": "Nombre d'ordinateurs en service", "type": "entier", "min": 0},
            {"code": "F04", "libelle": "L'établissement dispose-t-il d'une connexion Internet permanente ?", "type": "oui_non"},
            {"code": "F06", "libelle": "Type de connexion", "type": "choix", "si": {"question": "F04", "valeurs": ["oui"]},
             "choix": [["fibre", "Fibre optique"], ["adsl", "ADSL"], ["mobile", "Réseau mobile (4G, 5G)"],
                       ["satellite", "Satellite"]]},
        ],
    },
    {
        "code": "G", "titre": "Performance",
        "intro": "Indicateurs du contrat de performance ou, à défaut, du plan d'actions annuel.",
        "questions": [
            {"code": "G01", "libelle": "Nombre d'indicateurs suivis", "type": "entier", "min": 0},
            {"code": "G02", "libelle": "Nombre d'indicateurs dont la cible est atteinte", "type": "entier", "min": 0},
            {"code": "G03", "libelle": "Taux d'exécution des activités programmées", "type": "pourcentage"},
            {"code": "G04", "libelle": "Principaux indicateurs du contrat de performance", "type": "tableau",
             "obligatoire": False, "si": {"question": "B06", "valeurs": ["oui"]},
             "aide": "Jusqu'à 20 indicateurs : intitulé, valeur cible et valeur réalisée.",
             "colonnes": [{"code": "indicateur", "libelle": "Indicateur", "type": "texte"},
                          {"code": "cible", "libelle": "Cible", "type": "nombre"},
                          {"code": "realise", "libelle": "Réalisé", "type": "nombre"}]},
        ],
    },
    {
        "code": "H", "titre": "Numérique", "intro": "",
        "questions": [
            {"code": "H04", "libelle": "Logiciels de gestion utilisés", "type": "choix_multiple", "obligatoire": False,
             "choix": [["comptabilite", "Comptabilité"], ["paie", "Paie / RH"], ["courrier", "Gestion du courrier"],
                       ["metier", "Logiciel métier"], ["aucun", "Aucun"]]},
            {"code": "H05", "libelle": "L'établissement propose-t-il des services en ligne aux usagers ?", "type": "oui_non"},
            {"code": "H06", "libelle": "Services en ligne proposés", "type": "texte_long",
             "si": {"question": "H05", "valeurs": ["oui"]}},
            {"code": "H07", "libelle": "Mesures de sécurité informatique en place", "type": "choix_multiple",
             "choix": [["antivirus", "Antivirus"], ["sauvegardes", "Sauvegardes régulières"], ["pare_feu", "Pare-feu"],
                       ["mots_de_passe", "Politique de mots de passe"], ["sensibilisation", "Sensibilisation du personnel"],
                       ["aucune", "Aucune"]]},
        ],
    },
    {
        "code": "I", "titre": "Difficultés et besoins", "intro": "",
        "questions": [
            {"code": "I01", "libelle": "Principales difficultés rencontrées", "type": "choix_multiple",
             "choix": [["financieres", "Financières"], ["humaines", "Ressources humaines"], ["materielles", "Matérielles"],
                       ["juridiques", "Juridiques ou réglementaires"], ["numeriques", "Numériques"], ["autres", "Autres"]]},
            {"code": "I02", "libelle": "Intensité des difficultés au cours de l'exercice", "type": "echelle",
             "min": 1, "max": 5, "libelle_min": "Très faible", "libelle_max": "Très forte"},
            {"code": "I03", "libelle": "Besoins prioritaires pour l'exercice suivant", "type": "texte_long"},
            {"code": "I04", "libelle": "Propositions et observations", "type": "texte_long", "obligatoire": False},
        ],
    },
    {
        "code": "J", "titre": "Pièces justificatives",
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

REGLES_PAR_DEFAUT = [
    {"type": "somme", "total": "D01", "parties": ["D02", "D03"]},
    {"type": "somme", "total": "D01", "parties": ["D04", "D05"]},
    {"type": "somme", "total": "D01", "parties": ["D09", "D10"]},
    {"type": "somme", "total": "D01", "parties": ["D11", "D12", "D13"]},
    {"type": "inferieur", "petit": "G02", "grand": "G01"},
]


def definition_par_defaut():
    return {"version": 1, "modules": copy.deepcopy(MODULES_PAR_DEFAUT), "regles": copy.deepcopy(REGLES_PAR_DEFAUT)}


def _nombre(v):
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def _milliers(n):
    return f"{n:,}".replace(",", " ")


def condition_remplie(q, donnees):
    """Vrai si la question doit être posée, compte tenu des réponses déjà données (F-13)."""
    si = q.get("si")
    if not si:
        return True
    valeur = donnees.get(si.get("question"))
    attendues = set(si.get("valeurs") or [])
    if isinstance(valeur, list):
        return bool(attendues & set(valeur))
    return valeur in attendues


class Questionnaire:
    """Lecture d'une définition de questionnaire (celle d'une campagne)."""

    def __init__(self, definition=None):
        self.definition = definition or definition_par_defaut()

    @property
    def version(self):
        return self.definition.get("version", 1)

    @property
    def tous_les_modules(self):
        return self.definition.get("modules", [])

    @property
    def modules(self):
        """Modules actifs seulement : un module désactivé n'est ni posé, ni exporté, ni compté."""
        return [m for m in self.tous_les_modules if m.get("actif", True)]

    @property
    def regles(self):
        return self.definition.get("regles", [])

    def codes_modules(self):
        return [m["code"] for m in self.modules]

    def module(self, code):
        return next((m for m in self.modules if m["code"] == code), None)

    def questions(self):
        for m in self.modules:
            for q in m["questions"]:
                yield m, q

    def question(self, code):
        return next((q for _, q in self.questions() if q["code"] == code), None)

    def module_de(self, code_question):
        return next((m for m, q in self.questions() if q["code"] == code_question), None)

    def regles_du_module(self, code_module):
        """Règles dont au moins une question appartient au module : [(codes à signaler, fonction(donnees))]."""
        codes = {q["code"] for q in (self.module(code_module) or {}).get("questions", [])}
        sortie = []
        for regle in self.regles:
            champs, fonction = self._compiler(regle)
            if fonction and codes & set(champs):
                sortie.append((tuple(c for c in champs if c in codes), fonction))
        return sortie

    def _libelle(self, code):
        q = self.question(code)
        return q["libelle"].lower() if q else code

    def _compiler(self, regle):
        if regle.get("type") == "somme":
            total, parties = regle.get("total"), list(regle.get("parties") or [])

            def somme(d):
                valeurs = [_nombre(d.get(p)) for p in parties]
                t = _nombre(d.get(total))
                if t is None or any(v is None for v in valeurs) or sum(valeurs) == t:
                    return None
                noms = " + ".join(self._libelle(p) for p in parties)
                return regle.get("message") or (
                    f"{noms[:1].upper()}{noms[1:]} = {_milliers(sum(valeurs))}, différent de « {self._libelle(total)} » "
                    f"({_milliers(t)}).")
            return parties, somme
        if regle.get("type") == "inferieur":
            petit, grand = regle.get("petit"), regle.get("grand")

            def inferieur(d):
                a, b = _nombre(d.get(petit)), _nombre(d.get(grand))
                if a is None or b is None or a <= b:
                    return None
                return regle.get("message") or (
                    f"« {self._libelle(petit)[:1].upper()}{self._libelle(petit)[1:]} » ne peut pas dépasser "
                    f"« {self._libelle(grand)} ».")
            return [petit], inferieur
        return [], None


def libelle_reponse(q, valeur):
    """Valeur lisible pour l'affichage et l'export Excel."""
    if valeur in (None, "", []):
        return ""
    if q["type"] == "oui_non":
        return dict(OUI_NON).get(valeur, valeur)
    if q["type"] == "choix":
        return dict(map(tuple, q["choix"])).get(valeur, valeur)
    if q["type"] == "choix_multiple":
        libelles = dict(map(tuple, q["choix"]))
        return ", ".join(libelles.get(v, v) for v in valeur)
    if q["type"] == "tableau":
        colonnes = q.get("colonnes", [])
        return " ; ".join(" · ".join(str(l.get(c["code"], "")) for c in colonnes) for l in valeur if isinstance(l, dict))
    if q["type"] == "date" and isinstance(valeur, str) and len(valeur) == 10:
        a, m, j = valeur.split("-")
        return f"{j}/{m}/{a}"
    return valeur


def affichage(q, valeur):
    """Valeur mise en forme pour les récapitulatifs à l'écran (milliers séparés, pourcentages…)."""
    if valeur in (None, "", []):
        return ""
    if q["type"] in ("entier", "montant") and not q.get("annee") and isinstance(valeur, (int, float)):
        texte = f"{valeur:,.2f}".rstrip("0").rstrip(".") if isinstance(valeur, float) else f"{valeur:,}"
        return texte.replace(",", " ").replace(".", ",")
    if q["type"] == "pourcentage":
        return f"{valeur} %".replace(".", ",")
    if q["type"] == "echelle":
        return f"{valeur} / {q.get('max', 5)}"
    return str(libelle_reponse(q, valeur))
