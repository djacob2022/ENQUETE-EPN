"""Récapitulatif officiel d'une réponse au format PDF (F-27) : en-tête de l'institution, réponses par rubrique,
pièces jointes, certification. Joint à l'accusé de réception et téléchargeable par l'établissement et l'équipe."""
from io import BytesIO
from xml.sax.saxutils import escape

from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Image, KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .models import Parametres
from .questionnaire import affichage, condition_remplie

VERT = colors.HexColor("#073625")
MARQUE = colors.HexColor("#007a4d")
TRAIT = colors.HexColor("#dde3de")
DISCRET = colors.HexColor("#4d5a53")


def _t(texte):
    """Texte sûr pour les polices standard du PDF (jeu Windows-1252) et pour le balisage de ReportLab."""
    texte = str(texte if texte is not None else "").replace(" ", " ").replace(" ", " ")
    texte = texte.encode("cp1252", "replace").decode("cp1252")
    return escape(texte).replace("\n", "<br/>")


def _styles():
    base = getSampleStyleSheet()
    return {
        "pays": ParagraphStyle("pays", parent=base["Normal"], fontName="Helvetica-Bold", fontSize=9, textColor=VERT,
                               alignment=TA_CENTER, leading=11),
        "devise": ParagraphStyle("devise", parent=base["Normal"], fontName="Helvetica-Oblique", fontSize=8,
                                 textColor=DISCRET, alignment=TA_CENTER),
        "titre": ParagraphStyle("titre", parent=base["Title"], fontName="Helvetica-Bold", fontSize=16, textColor=VERT,
                                spaceBefore=6, spaceAfter=2),
        "sous": ParagraphStyle("sous", parent=base["Normal"], fontSize=9.5, textColor=DISCRET, alignment=TA_CENTER),
        "rubrique": ParagraphStyle("rubrique", parent=base["Heading3"], fontName="Helvetica-Bold", fontSize=11,
                                   textColor=MARQUE, spaceBefore=10, spaceAfter=4),
        "cellule": ParagraphStyle("cellule", parent=base["Normal"], fontSize=8.5, leading=10.5),
        "valeur": ParagraphStyle("valeur", parent=base["Normal"], fontName="Helvetica-Bold", fontSize=8.5, leading=10.5),
        "texte": ParagraphStyle("texte", parent=base["Normal"], fontSize=9, leading=12),
    }


def _pied(canvas, doc, mention):
    canvas.saveState()
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(DISCRET)
    canvas.drawString(18 * mm, 10 * mm, mention.encode("cp1252", "replace").decode("cp1252"))
    canvas.drawRightString(A4[0] - 18 * mm, 10 * mm, f"Page {doc.page}")
    canvas.setStrokeColor(MARQUE)
    canvas.setLineWidth(2)
    canvas.line(18 * mm, A4[1] - 10 * mm, A4[0] - 18 * mm, A4[1] - 10 * mm)
    canvas.restoreState()


def recapitulatif(reponse):
    p = Parametres.charger()
    s = _styles()
    tampon = BytesIO()
    genere = timezone.localtime().strftime("%d/%m/%Y à %H:%M")
    doc = SimpleDocTemplate(tampon, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm,
                            bottomMargin=18 * mm, title=f"Récapitulatif – {reponse.epn.nom}", author=p.valeur("institution"))
    elements = []
    if p.logo:
        try:
            elements.append(Image(p.logo.path, width=18 * mm, height=18 * mm, kind="proportional"))
        except Exception:  # logo illisible : le document reste produit
            pass
    elements += [Paragraph(_t(p.valeur("pays")).upper(), s["pays"]), Paragraph(_t(p.valeur("devise")), s["devise"]),
                 Spacer(1, 3), Paragraph(_t(p.valeur("ministere")), s["sous"]), Spacer(1, 8),
                 Paragraph(_t("Récapitulatif des réponses"), s["titre"]),
                 Paragraph(_t(f"{reponse.campagne.nom} · exercice {reponse.campagne.exercice}"), s["sous"]), Spacer(1, 10)]

    statut = reponse.get_statut_display()
    soumis = timezone.localtime(reponse.date_soumission).strftime("%d/%m/%Y à %H:%M") if reponse.date_soumission else "—"
    infos = [
        ("Établissement", f"{reponse.epn.nom}" + (f" ({reponse.epn.sigle})" if reponse.epn.sigle else "")),
        ("Tutelle · catégorie", f"{reponse.epn.tutelle} · {reponse.epn.categorie}"),
        ("Répondant", f"{reponse.repondant or '—'}" + (f", {reponse.fonction}" if reponse.fonction else "")),
        ("Contact", " · ".join(x for x in (reponse.email, reponse.telephone) if x) or "—"),
        ("Statut", statut), ("Envoyé le", soumis),
    ]
    t = Table([[Paragraph(_t(k), s["cellule"]), Paragraph(_t(v), s["valeur"])] for k, v in infos],
              colWidths=[42 * mm, None])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f2f6f3")),
                           ("BOX", (0, 0), (-1, -1), 0.5, TRAIT), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                           ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
    elements += [t, Spacer(1, 6)]

    pieces = {pj.code: pj for pj in reponse.pieces.all()}
    for module in reponse.campagne.q.modules:
        lignes = []
        for q in module["questions"]:
            if not condition_remplie(q, reponse.donnees):
                continue
            if q["type"] == "fichier":
                pj = pieces.get(q["code"])
                valeur = f"{pj.nom_original} ({pj.taille // 1024} Ko)" if pj else ""
            else:
                valeur = affichage(q, reponse.donnees.get(q["code"]))
            lignes.append([Paragraph(_t(q["code"]), s["cellule"]), Paragraph(_t(q["libelle"]), s["cellule"]),
                           Paragraph(_t(valeur or "Non renseigné"), s["valeur"] if valeur else s["cellule"])])
        if not lignes:
            continue
        tableau = Table(lignes, colWidths=[13 * mm, 82 * mm, None], repeatRows=0)
        tableau.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, -1), 0.3, TRAIT), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                                     ("TEXTCOLOR", (0, 0), (0, -1), DISCRET), ("TOPPADDING", (0, 0), (-1, -1), 3),
                                     ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]))
        elements += [KeepTogether([Paragraph(_t(f"{module['code']}. {module['titre']}"), s["rubrique"]), tableau])]

    elements += [Spacer(1, 12), Paragraph(_t(
        f"Je soussigné(e), {reponse.repondant or '—'}{', ' + reponse.fonction if reponse.fonction else ''}, certifie "
        f"l'exactitude et l'exhaustivité des informations transmises pour {reponse.epn.nom}."
        if reponse.date_soumission else "Réponse non encore envoyée : document provisoire."), s["texte"])]
    mention = f"{p.valeur('institution')} · ENQUÊTE-EPN · document généré le {genere}"
    doc.build(elements, onFirstPage=lambda c, d: _pied(c, d, mention), onLaterPages=lambda c, d: _pied(c, d, mention))
    return tampon.getvalue()


def nom_fichier(reponse):
    from django.utils.text import get_valid_filename

    return f"Recapitulatif_{get_valid_filename(reponse.epn.sigle or reponse.epn.nom)}_{reponse.campagne.exercice}.pdf"
