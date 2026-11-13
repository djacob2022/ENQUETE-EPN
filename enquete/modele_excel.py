"""Modèle Excel hors ligne (F-26) : l'établissement télécharge le questionnaire, le remplit sans connexion,
puis le réimporte. Les réponses passent par les mêmes contrôles que la saisie en ligne (brouillon conservé)."""
import datetime
from io import BytesIO

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill, Protection
from openpyxl.worksheet.datavalidation import DataValidation

from .questionnaire import OUI_NON, OUI_NON_EN, TYPES, oui_non

ENTETE = Font(bold=True, color="FFFFFF")
FOND = PatternFill("solid", fgColor="073625")
SAISIE = PatternFill("solid", fgColor="FFF8E6")
COLONNES = ["Rubrique", "Code", "Question", "Type", "Obligatoire", "Choix possibles / aide", "Votre réponse"]
TYPES_EN = {"texte": "Short text", "texte_long": "Long text", "entier": "Whole number", "montant": "Amount",
            "pourcentage": "Percentage", "date": "Date", "choix": "Single choice", "choix_multiple": "Multiple choice",
            "oui_non": "Yes / no", "echelle": "Scale", "tableau": "Repeating table", "url": "Web address",
            "fichier": "Attached file"}
TEXTES_EN = {
    "Lisez-moi": "Read me", "Rubrique": "Section", "Type": "Type", "Obligatoire": "Required",
    "Choix possibles / aide": "Possible choices / help", "Votre réponse": "Your answer", "oui": "yes", "non": "no",
    "À compléter en ligne": "To be completed online", "Valeur non prévue": "Unexpected value",
    "Choisissez une valeur dans la liste.": "Choose a value from the list.",
    "1. Remplissez uniquement la colonne « Votre réponse » (en jaune) de la feuille « Questionnaire ».":
        "1. Only fill in the “Your answer” column (in yellow) of the “Questionnaire” sheet.",
    "2. Pour les listes, choisissez dans le menu déroulant. Choix multiples : séparez par « ; ».":
        "2. For lists, choose from the drop-down menu. Multiple choices: separate with “;”.",
    "3. Montants et nombres : chiffres seuls, sans unité. Dates : JJ/MM/AAAA.":
        "3. Amounts and numbers: digits only, no unit. Dates: DD/MM/YYYY.",
    "4. Les tableaux et les pièces justificatives se complètent en ligne.":
        "4. Tables and supporting documents are completed online.",
    "5. Revenez sur votre lien personnel, puis « Importer le fichier Excel » : vos réponses sont vérifiées "
    "et enregistrées en brouillon. Relisez et envoyez en ligne.":
        "5. Go back to your personal link, then “Import the Excel file”: your answers are checked and saved as a "
        "draft. Review and submit online.",
    "Ne modifiez ni les codes ni l'ordre des lignes.": "Do not change the codes or the order of the rows.",
}


def _x(texte):
    from .langue import anglais

    return TEXTES_EN.get(texte, texte) if anglais() else texte
NON_IMPORTABLES = {"fichier", "tableau"}
SEPARATEUR = " ; "


def _choix(q):
    if q["type"] == "oui_non":
        return oui_non()
    return q.get("choix", [])


def _valeur_cellule(q, v):
    if v in (None, "", []):
        return None
    if q["type"] == "date" and isinstance(v, str):
        try:
            return datetime.date.fromisoformat(v)
        except ValueError:
            return v
    if q["type"] in ("choix", "oui_non"):
        return dict(map(tuple, _choix(q))).get(v, v)
    if q["type"] == "choix_multiple":
        libelles = dict(map(tuple, _choix(q)))
        return SEPARATEUR.join(libelles.get(x, x) for x in v)
    return v


def generer(reponse):
    from .langue import anglais

    q = reponse.campagne.q
    wb = Workbook()
    lisez = wb.active
    lisez.title = _x("Lisez-moi")
    for ligne in [
        [f"Questionnaire {reponse.campagne.nom} – {reponse.epn.nom}"], [],
        [_x("1. Remplissez uniquement la colonne « Votre réponse » (en jaune) de la feuille « Questionnaire ».")],
        [_x("2. Pour les listes, choisissez dans le menu déroulant. Choix multiples : séparez par « ; ».")],
        [_x("3. Montants et nombres : chiffres seuls, sans unité. Dates : JJ/MM/AAAA.")],
        [_x("4. Les tableaux et les pièces justificatives se complètent en ligne.")],
        [_x("5. Revenez sur votre lien personnel, puis « Importer le fichier Excel » : vos réponses sont vérifiées "
         "et enregistrées en brouillon. Relisez et envoyez en ligne.")],
        [], [_x("Ne modifiez ni les codes ni l'ordre des lignes.")],
    ]:
        lisez.append(ligne)
    lisez["A1"].font = Font(bold=True, size=13, color="073625")
    lisez.column_dimensions["A"].width = 110

    ws = wb.create_sheet("Questionnaire")
    ws.append([_x(c) for c in COLONNES])
    for c in ws[1]:
        c.font, c.fill = ENTETE, FOND
        c.alignment = Alignment(vertical="center", wrap_text=True)
    listes = {}
    for module, question in q.questions():
        t = question["type"]
        if t in NON_IMPORTABLES:
            aide = _x("À compléter en ligne")
        elif t in ("choix", "oui_non", "choix_multiple"):
            aide = SEPARATEUR.join(l for _, l in _choix(question))
        elif t == "echelle":
            aide = (f"Number from {question.get('min', 1)} to {question.get('max', 5)}" if anglais() else
                    f"Nombre de {question.get('min', 1)} à {question.get('max', 5)}")
        else:
            aide = question.get("aide") or (f"{'In' if anglais() else 'En'} {question['unite']}"
                                            if question.get("unite") else "")
        ws.append([f"{module['code']}. {module['titre']}", question["code"], question["libelle"],
                   (TYPES_EN if anglais() else TYPES).get(t, t), _x("oui" if question.get("obligatoire", True) else "non"),
                   aide,
                   None if t in NON_IMPORTABLES else _valeur_cellule(question, reponse.donnees.get(question["code"]))])
        cellule = ws.cell(row=ws.max_row, column=7)
        if t in NON_IMPORTABLES:
            continue
        cellule.fill = SAISIE
        cellule.protection = Protection(locked=False)
        if t == "date":
            cellule.number_format = "dd/mm/yyyy"
        if t in ("choix", "oui_non"):
            options = '"' + ",".join(l.replace(",", " ").replace('"', "'") for _, l in _choix(question)) + '"'
            if len(options) <= 255:  # limite d'Excel pour une liste en ligne
                listes.setdefault(options, []).append(cellule.coordinate)
    for options, cellules in listes.items():
        dv = DataValidation(type="list", formula1=options, allow_blank=True, showErrorMessage=True,
                            errorTitle=_x("Valeur non prévue"), error=_x("Choisissez une valeur dans la liste."))
        ws.add_data_validation(dv)
        for c in cellules:
            dv.add(c)
    for col, largeur in zip("ABCDEFG", (26, 7, 60, 16, 11, 40, 38)):
        ws.column_dimensions[col].width = largeur
    for ligne in ws.iter_rows(min_row=2):
        for c in ligne:
            c.alignment = Alignment(vertical="top", wrap_text=True)
    ws.freeze_panes = "C2"
    ws.protection.sheet = True  # seules les cellules jaunes sont modifiables
    ws.protection.formatColumns = False
    wb.active = 1
    tampon = BytesIO()
    wb.save(tampon)
    return tampon.getvalue()


def _depuis_cellule(q, v):
    """Valeur Excel → valeur attendue par la saisie en ligne (codes des choix, date ISO, nombre en texte)."""
    if v is None or (isinstance(v, str) and not v.strip()):
        return None
    t = q["type"]
    if isinstance(v, (datetime.datetime, datetime.date)):
        return v.date().isoformat() if isinstance(v, datetime.datetime) else v.isoformat()
    if t == "date" and isinstance(v, str):
        try:
            j, m, a = v.strip().split("/")
            return f"{int(a):04d}-{int(m):02d}-{int(j):02d}"
        except ValueError:
            return v.strip()
    if t in ("choix", "oui_non", "choix_multiple"):
        # Libellés français et anglais acceptés : le fichier peut avoir été téléchargé dans l'autre langue (F-16).
        from .questionnaire_en import EN

        inverse = {v: k for k, v in EN.items()}
        par_libelle = {}
        for c, l in _choix(q) + (OUI_NON + OUI_NON_EN if t == "oui_non" else []):
            for variante in (l, EN.get(l, l), inverse.get(l, l)):
                par_libelle.setdefault(variante.strip().lower(), c)
        codes = {c.lower(): c for c, _ in _choix(q)}
        morceaux = [m.strip() for m in str(v).split(";")] if t == "choix_multiple" else [str(v).strip()]
        valeurs = [par_libelle.get(m.lower()) or codes.get(m.lower()) or m for m in morceaux if m]
        return valeurs if t == "choix_multiple" else valeurs[0]
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    return str(v).strip()


def importer(reponse, fichier):
    """Lit le modèle rempli et enregistre les réponses rubrique par rubrique. Renvoie (nombre, erreurs)."""
    from .services import Refus, enregistrer_module

    if not fichier.name.lower().endswith(".xlsx"):
        raise Refus("Choisissez le fichier Excel (.xlsx) téléchargé depuis votre questionnaire.")
    if fichier.size > 5 * 1024 * 1024:
        raise Refus("Fichier trop volumineux (5 Mo maximum).")
    try:
        wb = load_workbook(fichier, read_only=True, data_only=True)
        ws = wb["Questionnaire"]
    except Exception:
        raise Refus("Ce fichier n'est pas le modèle du questionnaire : téléchargez-le à nouveau depuis votre lien.")
    q = reponse.campagne.q
    par_module = {}
    for ligne in ws.iter_rows(min_row=2, values_only=True):
        if not ligne or len(ligne) < 7 or not ligne[1]:
            continue
        code = str(ligne[1]).strip().upper()
        question = q.question(code)
        module = q.module_de(code)
        if question is None or question["type"] in NON_IMPORTABLES or ligne[6] is None:
            continue
        par_module.setdefault(module["code"], {})[code] = _depuis_cellule(question, ligne[6])
    if not par_module:
        raise Refus("Aucune réponse trouvée dans la colonne « Votre réponse ».")
    erreurs, nombre = {}, 0
    for code_module, valeurs in par_module.items():
        nombre += len(valeurs)
        erreurs.update(enregistrer_module(reponse, code_module, valeurs, valider=False))
    return nombre, erreurs, len(par_module)
