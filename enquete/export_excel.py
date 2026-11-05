"""Génération du classeur Excel : réponses consolidées, dictionnaire des variables, statistiques."""
import csv
import datetime
from io import BytesIO, StringIO

from django.utils import timezone
from openpyxl import Workbook
from openpyxl.chart import BarChart, Reference
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from . import statistiques
from .questionnaire import TYPES, TYPES_NUMERIQUES, libelle_reponse

ENTETE = Font(bold=True, color="FFFFFF")
FOND_ENTETE = PatternFill("solid", fgColor="1D4E89")

COLONNES_FIXES = [
    ("EPN", lambda r: r.epn.nom),
    ("Sigle", lambda r: r.epn.sigle),
    ("Catégorie", lambda r: r.epn.categorie),
    ("Tutelle", lambda r: r.epn.tutelle),
    ("Région", lambda r: r.epn.region),
    ("Secteur", lambda r: r.epn.secteur),
    ("Statut", lambda r: r.get_statut_display()),
    ("Nom du répondant", lambda r: r.nom),
    ("Prénom du répondant", lambda r: r.prenom),
    ("Fonction", lambda r: r.fonction),
    ("E-mail", lambda r: r.email),
    ("Téléphone", lambda r: r.telephone),
    ("Date de soumission", lambda r: _heure(r.date_soumission)),
    ("Date de validation", lambda r: _heure(r.date_validation)),
]


def _heure(d):
    return timezone.localtime(d).replace(tzinfo=None) if d else None


DEBUTS_DE_FORMULE = ("=", "+", "-", "@", "\t", "\r")


def _ajouter(ws, valeurs):
    """Ajoute une ligne de données : un texte qui ressemble à une formule reste du texte.

    Sans cela, une réponse saisie comme « =HYPERLINK(…) » ou « =cmd|… » serait exécutée par Excel
    à l'ouverture du fichier par l'administration (injection de formules).
    """
    ws.append(valeurs)
    for cellule in ws[ws.max_row]:
        if isinstance(cellule.value, str) and cellule.value.startswith(DEBUTS_DE_FORMULE):
            cellule.data_type = "s"
            cellule.quotePrefix = True


def _entete(ws, valeurs):
    ws.append(valeurs)
    for cellule in ws[1]:
        cellule.font = ENTETE
        cellule.fill = FOND_ENTETE
        cellule.alignment = Alignment(vertical="center", wrap_text=True)
    ws.freeze_panes = "B2"
    ws.auto_filter.ref = ws.dimensions


def _largeurs(ws, largeur_max=45):
    for i, colonne in enumerate(ws.columns, start=1):
        longueur = max((len(str(c.value)) for c in colonne if c.value is not None), default=8)
        ws.column_dimensions[get_column_letter(i)].width = min(max(10, longueur + 2), largeur_max)


def _valeur_excel(q, valeur):
    if q["type"] in TYPES_NUMERIQUES or q["type"] == "echelle":
        return valeur  # reste un nombre dans Excel
    if q["type"] == "date" and isinstance(valeur, str):
        try:
            return datetime.date.fromisoformat(valeur)  # vraie date Excel
        except ValueError:
            return valeur
    return libelle_reponse(q, valeur)


def _formats(ws, questions, premiere_colonne, premiere_ligne=2):
    for i, q in enumerate(questions, start=premiere_colonne):
        fmt = {"montant": "#,##0", "date": "dd/mm/yyyy"}.get(q["type"])
        if fmt:
            for (c,) in ws.iter_rows(min_row=premiere_ligne, min_col=i, max_col=i):
                c.number_format = fmt


def classeur(campagne, reponses, statistiques_seules=False):
    """Classeur consolidé (F-34). `statistiques_seules` : sans les feuilles nominatives (rôle « lecteur »)."""
    wb = Workbook()
    questionnaire = campagne.q
    if statistiques_seules:
        wb.remove(wb.active)
        _feuilles_statistiques(wb, questionnaire, reponses)
        tampon = BytesIO()
        wb.save(tampon)
        return tampon.getvalue()

    # 1. Réponses : une ligne par EPN, une colonne par question.
    ws = wb.active
    ws.title = "Réponses"
    questions = [q for _, q in questionnaire.questions()]
    _entete(ws, [nom for nom, _ in COLONNES_FIXES] + [q["code"] for q in questions])
    for r in reponses:
        _ajouter(ws, [f(r) for _, f in COLONNES_FIXES] + [_valeur_excel(q, r.donnees.get(q["code"])) for q in questions])
    for ligne in ws.iter_rows(min_row=2, min_col=len(COLONNES_FIXES) - 1, max_col=len(COLONNES_FIXES)):
        for c in ligne:
            c.number_format = "dd/mm/yyyy hh:mm"
    _formats(ws, questions, len(COLONNES_FIXES) + 1)
    _largeurs(ws)

    # 2. Dictionnaire des variables.
    wd = wb.create_sheet("Dictionnaire")
    _entete(wd, ["Code", "Module", "Libellé", "Type", "Obligatoire", "Modalités"])
    for module, q in questionnaire.questions():
        _ajouter(wd, [q["code"], f"{module['code']}. {module['titre']}", q["libelle"], TYPES.get(q["type"], q["type"]),
                      "oui" if q.get("obligatoire", True) else "non", _modalites(q)])
    _largeurs(wd, 70)
    _feuilles_statistiques(wb, questionnaire, reponses)
    wb.properties.title = f"Export {campagne}"
    tampon = BytesIO()
    wb.save(tampon)
    return tampon.getvalue()


def _feuilles_statistiques(wb, questionnaire, reponses):
    # 3. Statistiques descriptives des variables numériques + graphique des moyennes RH.
    wsx = wb.create_sheet("Statistiques")
    _entete(wsx, ["Code", "Libellé", "n", "Somme", "Moyenne", "Médiane", "Minimum", "1er quartile", "3e quartile",
                  "Maximum", "Écart-type"])
    blocs = statistiques.par_question(questionnaire, reponses)
    for bloc in blocs:
        for item in bloc["questions"]:
            if item["genre"] != "numerique":
                continue
            s = item["stats"]
            _ajouter(wsx, [item["q"]["code"], item["q"]["libelle"], s["n"], s.get("somme"), s.get("moyenne"),
                           s.get("mediane"), s.get("min"), s.get("q1"), s.get("q3"), s.get("max"), s.get("ecart_type")])
    for ligne in wsx.iter_rows(min_row=2, min_col=4, max_col=11):
        for c in ligne:
            c.number_format = "#,##0.00"
    _largeurs(wsx, 60)

    # 3 bis. Fréquences des variables qualitatives (F-45).
    wf = wb.create_sheet("Fréquences")
    _entete(wf, ["Code", "Libellé", "Modalité", "Effectif", "Pourcentage", "n"])
    for bloc in blocs:
        for item in bloc["questions"]:
            if item["genre"] != "frequence":
                continue
            for l in item["stats"]["lignes"]:
                _ajouter(wf, [item["q"]["code"], item["q"]["libelle"], l["libelle"], l["effectif"],
                              round(l["pourcentage"], 1), item["stats"]["n"]])
    _largeurs(wf, 60)

    # 4. Indicateurs + graphique Excel natif.
    wi = wb.create_sheet("Indicateurs")
    _entete(wi, ["Indicateur", "Valeur (%)", "Mode de calcul"])
    for ind in statistiques.indicateurs(reponses):
        _ajouter(wi, [ind["libelle"], round(ind["valeur"], 1) if ind["valeur"] is not None else None, ind["formule"]])
    _largeurs(wi, 60)
    if reponses:
        graphique = BarChart()
        graphique.type = "bar"
        graphique.title = "Indicateurs clés (%)"
        graphique.legend = None
        graphique.y_axis.title = "%"
        donnees = Reference(wi, min_col=2, min_row=1, max_row=wi.max_row)
        categories = Reference(wi, min_col=1, min_row=2, max_row=wi.max_row)
        graphique.add_data(donnees, titles_from_data=True)
        graphique.set_categories(categories)
        graphique.width, graphique.height = 22, 10
        wi.add_chart(graphique, "E2")


def _modalites(q):
    if q["type"] == "oui_non":
        return "oui; non"
    if q["type"] == "echelle":
        return f"de {q.get('min', 1)} ({q.get('libelle_min', '')}) à {q.get('max', 5)} ({q.get('libelle_max', '')})"
    if q["type"] == "tableau":
        return "colonnes : " + ", ".join(c["libelle"] for c in q.get("colonnes", []))
    return "; ".join(f"{c} = {lib}" for c, lib in q.get("choix", []))


def classeur_reponse(reponse):
    """La réponse d'un EPN (F-33) : une feuille de synthèse, puis une feuille par module."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Synthèse"
    _entete(ws, ["Rubrique", "Valeur"])
    for nom, f in COLONNES_FIXES:
        _ajouter(ws, [nom, f(reponse)])
    ws.cell(row=ws.max_row - 1, column=2).number_format = "dd/mm/yyyy hh:mm"
    ws.cell(row=ws.max_row, column=2).number_format = "dd/mm/yyyy hh:mm"
    _ajouter(ws, ["Campagne", str(reponse.campagne)])
    _ajouter(ws, ["Exercice", reponse.campagne.exercice])
    _largeurs(ws, 70)
    for module in reponse.campagne.q.modules:
        titre = f"{module['code']}. {module['titre']}"[:31].replace("/", "-")
        wm = wb.create_sheet(titre)
        _entete(wm, ["Code", "Question", "Réponse"])
        for q in module["questions"]:
            _ajouter(wm, [q["code"], q["libelle"], _valeur_excel(q, reponse.donnees.get(q["code"]))])
            fmt = {"montant": "#,##0", "date": "dd/mm/yyyy"}.get(q["type"])
            if fmt:
                wm.cell(row=wm.max_row, column=3).number_format = fmt
        _largeurs(wm, 80)
    wb.properties.title = f"{reponse.epn} – {reponse.campagne}"
    tampon = BytesIO()
    wb.save(tampon)
    return tampon.getvalue()


def csv_reponses(campagne, reponses):
    """Export CSV UTF-8 (F-37) pour SPSS, Stata ou R : codes bruts des modalités, séparateur point-virgule."""
    questions = [q for _, q in campagne.q.questions()]
    tampon = StringIO()
    tampon.write("\ufeff")  # BOM : Excel reconnaît l'UTF-8
    ecrivain = csv.writer(tampon, delimiter=";", lineterminator="\n")
    ecrivain.writerow(["epn", "sigle", "categorie", "tutelle", "region", "statut"] + [q["code"] for q in questions])

    def brut(q, v):
        if v in (None, "", []):
            return ""
        if isinstance(v, list):
            return libelle_reponse(q, v) if q["type"] == "tableau" else "|".join(map(str, v))
        texte = str(v)
        return "'" + texte if texte.startswith(DEBUTS_DE_FORMULE) else texte

    for r in reponses:
        ecrivain.writerow([brut({}, r.epn.nom), r.epn.sigle, r.epn.categorie, r.epn.tutelle, r.epn.region, r.statut]
                          + [brut(q, r.donnees.get(q["code"])) for q in questions])
    return tampon.getvalue().encode("utf-8")


def classeur_liens(campagne, reponses):
    """Liste des liens personnels, prête pour un publipostage (une ligne par EPN)."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Liens"
    _entete(ws, ["EPN", "Sigle", "Tutelle", "E-mail du point focal", "Lien personnel", "Statut"])
    for r in reponses:
        _ajouter(ws, [r.epn.nom, r.epn.sigle, r.epn.tutelle, r.epn.email_contact, r.lien, r.get_statut_display()])
        cellule = ws.cell(row=ws.max_row, column=5)
        cellule.hyperlink = r.lien
        cellule.style = "Hyperlink"
    _largeurs(ws, 70)
    wb.properties.title = f"Liens {campagne}"
    tampon = BytesIO()
    wb.save(tampon)
    return tampon.getvalue()


def nom_fichier(campagne):
    return f"EPN_{campagne.exercice}_{timezone.localdate():%Y-%m-%d}.xlsx"


def lire_epn(fichier):
    """Lit un fichier Excel d'EPN. Renvoie (lignes valides, erreurs)."""
    from openpyxl import load_workbook

    wb = load_workbook(fichier, read_only=True, data_only=True)
    ws = wb.active
    lignes, erreurs = [], []
    for num, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
        if not row or not any(row):
            continue
        valeurs = [(str(v).strip() if v is not None else "") for v in list(row) + [None] * 8][:8]
        nom, sigle, categorie, tutelle, region, email, secteur, etat = valeurs
        categorie = categorie.upper() or "EPA"
        if not nom or not tutelle or "@" not in email:
            erreurs.append(f"Ligne {num} : dénomination, tutelle et e-mail valide sont obligatoires.")
            continue
        if categorie not in ("EPA", "EPIC", "AUTRE"):
            erreurs.append(f"Ligne {num} : catégorie « {categorie} » inconnue (EPA, EPIC ou AUTRE).")
            continue
        etats = {"actif": "actif", "en liquidation": "liquidation", "liquidation": "liquidation", "dissous": "dissous"}
        if etat and etat.lower() not in etats:
            erreurs.append(f"Ligne {num} : statut « {etat} » inconnu (Actif, En liquidation ou Dissous).")
            continue
        lignes.append({"nom": nom, "sigle": sigle, "categorie": categorie, "tutelle": tutelle,
                       "region": region, "email_contact": email, "secteur": secteur,
                       "etat": etats.get(etat.lower(), "actif")})
    return lignes, erreurs

