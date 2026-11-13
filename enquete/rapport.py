"""Rapport annuel automatique d'une campagne, au format PDF.

Produit à partir des seules données agrégées : participation (globale, par tutelle, catégorie et région), indicateurs
de la section 6.3 comparés à l'exercice précédent, statistiques par rubrique, difficultés et besoins, contrôle qualité
(valeurs atypiques, sans nom d'établissement). Des constats sont rédigés automatiquement à partir des chiffres ; si
l'assistant IA est configuré, sa synthèse (analyse, points forts, points de vigilance, recommandations) s'y ajoute.

Téléchargeable à tout moment par l'équipe (périmètre de chaque compte), et envoyé automatiquement aux administrateurs
après la clôture de la campagne (commande « taches »).
"""
from collections import Counter
from io import BytesIO

from django.utils import timezone
from reportlab.graphics.charts.barcharts import HorizontalBarChart, VerticalBarChart
from reportlab.graphics.shapes import Drawing, String
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (CondPageBreak, Image, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer,
                                Table, TableStyle)

from . import statistiques
from .models import Parametres, Reponse
from .pdf import DISCRET, MARQUE, TRAIT, VERT, _pied, _styles, _t

GRIS = colors.HexColor("#b9c4bd")
FOND = colors.HexColor("#f2f6f3")
BASES_LIBELLES = {"validees": "réponses validées", "envoyees": "réponses envoyées", "toutes": "toutes les réponses"}
LIBRES = ("texte_long",)


# --- Données ---------------------------------------------------------------------------------------------------------

def collecter(campagne, toutes, base="validees", precedente=None, toutes_precedentes=None, perimetre=None):
    """Rassemble les chiffres du rapport. `toutes` : réponses de la campagne dans le périmètre (tous statuts)."""
    toutes = list(toutes)
    statuts = {"validees": ("valide",), "envoyees": Reponse.ENVOYES}.get(base)
    rep = [r for r in toutes if statuts is None or r.statut in statuts]
    prec = None
    if precedente is not None and toutes_precedentes is not None:
        prec = [r for r in toutes_precedentes if statuts is None or r.statut in statuts]
    soumis = sum(1 for r in toutes if r.est_soumise)
    indic = statistiques.indicateurs(rep)
    indic_prec = statistiques.indicateurs(prec) if prec else None
    for i, ligne in enumerate(indic):
        ligne["precedent"] = indic_prec[i]["valeur"] if indic_prec else None
    return {
        "campagne": campagne, "precedente": precedente, "base": base, "perimetre": perimetre or [],
        "toutes": toutes, "reponses": rep, "precedentes": prec,
        "participation": {
            "invites": len(toutes), "soumis": soumis, "valides": sum(1 for r in toutes if r.statut == "valide"),
            "taux": round(100 * soumis / len(toutes)) if toutes else 0,
            "statuts": Counter(r.get_statut_display() for r in toutes).most_common(),
            "par_tutelle": statistiques.taux_par_groupe(toutes, "tutelle"),
            "par_categorie": statistiques.taux_par_groupe(toutes, "categorie"),
            "par_region": statistiques.taux_par_groupe(toutes, "region"),
        },
        "indicateurs": indic,
        "blocs": statistiques.par_question(campagne.q, rep, prec),
        "atypiques": statistiques.valeurs_atypiques(campagne.q, rep),
    }


def questions_libres(campagne):
    return [q for _, q in campagne.q.questions() if q["type"] in LIBRES]


def _fmt(v, decimales=0, unite=""):
    if v is None:
        return "—"
    if isinstance(v, float) and decimales == 0 and abs(v) < 100 and v != int(v):
        decimales = 1
    texte = f"{v:,.{decimales}f}".replace(",", " ").replace(".", ",")
    return f"{texte}{unite}"


def _variation(v, p):
    if v is None or p is None:
        return "—"
    d = v - p
    return f"{'+' if d >= 0 else ''}{_fmt(d, 1)} pt"


def constats(d):
    """Constats rédigés automatiquement à partir des chiffres (toujours présents, même sans assistant IA)."""
    p = d["participation"]
    c = d["campagne"]
    sortie = [f"{p['soumis']} établissement(s) sur {p['invites']} ont transmis leur réponse, soit un taux de réponse de "
              f"{p['taux']} % ; {p['valides']} réponse(s) ont été validées par l'équipe d'enquête."]
    tut = [l for l in p["par_tutelle"] if l["total"] >= 2]
    if len(tut) >= 2:
        sortie.append(f"La participation varie selon la tutelle : de {tut[-1]['taux']} % ({tut[-1]['libelle']}) à "
                      f"{tut[0]['taux']} % ({tut[0]['libelle']}).")
    for i in d["indicateurs"]:
        if i["valeur"] is None:
            continue
        phrase = f"{i['libelle']} : {_fmt(i['valeur'], 1)} %"
        if i["precedent"] is not None:
            ecart = i["valeur"] - i["precedent"]
            if abs(ecart) >= 0.5:
                phrase += (f", en {'hausse' if ecart > 0 else 'baisse'} de {_fmt(abs(ecart), 1)} point(s) par rapport à "
                           f"l'exercice {d['precedente'].exercice}")
            else:
                phrase += f", stable par rapport à l'exercice {d['precedente'].exercice}"
        sortie.append(phrase + ".")
    q01 = c.q.question("I01")
    if q01:
        freq = statistiques.frequences(q01, [r.donnees.get("I01") for r in d["reponses"]])
        if freq["n"]:
            top = sorted(freq["lignes"], key=lambda l: -l["effectif"])[:2]
            sortie.append("Difficultés les plus citées : " + " et ".join(
                f"{l['libelle'].lower()} ({_fmt(l['pourcentage'])} % des établissements)" for l in top if l["effectif"]) + ".")
    q02 = c.q.question("I02")
    if q02:
        s = statistiques.descriptifs([r.donnees.get("I02") for r in d["reponses"]])
        if s["n"]:
            sortie.append(f"Intensité moyenne des difficultés ressentie : {_fmt(s['moyenne'], 1)} sur {q02.get('max', 5)}.")
    if d["atypiques"]:
        n_epn = len({a["reponse"] for a in d["atypiques"]})
        sortie.append(f"Contrôle qualité : {len(d['atypiques'])} valeur(s) atypique(s) relevée(s) chez {n_epn} "
                      f"établissement(s), à vérifier avant diffusion des résultats.")
    if not d["reponses"]:
        sortie.append(f"Aucune réponse ne correspond à la base retenue ({BASES_LIBELLES.get(d['base'], d['base'])}) : "
                      "les statistiques ci-après sont vides.")
    return sortie


# --- Graphiques ------------------------------------------------------------------------------------------------------

def _court(texte, n=28):
    texte = str(texte)
    return texte if len(texte) <= n else texte[: n - 1] + "…"


def _barres_horizontales(lignes, cle_libelle, cle_valeur, maximum=100, largeur=170 * mm, suffixe=" %"):
    lignes = lignes[:12]
    hauteur = 14 + 15 * len(lignes)
    d = Drawing(largeur, hauteur + 10)
    g = HorizontalBarChart()
    g.x, g.y, g.width, g.height = 62 * mm, 6, largeur - 62 * mm - 14 * mm, hauteur
    g.data = [[l[cle_valeur] or 0 for l in reversed(lignes)]]
    g.categoryAxis.categoryNames = [_court(l[cle_libelle]).encode("cp1252", "replace").decode("cp1252")
                                    for l in reversed(lignes)]
    g.categoryAxis.labels.fontSize = 7.5
    g.categoryAxis.labels.dx = -4
    g.categoryAxis.strokeColor = TRAIT
    g.valueAxis.valueMin, g.valueAxis.valueMax = 0, maximum or 1
    g.valueAxis.valueStep = (maximum or 1) / 4
    g.valueAxis.labels.fontSize = 7
    g.valueAxis.strokeColor = TRAIT
    g.valueAxis.visibleGrid, g.valueAxis.gridStrokeColor = True, colors.HexColor("#e8ece9")
    g.bars[0].fillColor, g.bars[0].strokeColor = MARQUE, None
    g.barLabelFormat = lambda v: _fmt(v) + suffixe
    g.barLabels.fontSize, g.barLabels.nudge, g.barLabels.boxAnchor = 7, 12, "w"
    d.add(g)
    return d


def _barres_comparees(indicateurs, annee, annee_prec, largeur=170 * mm):
    lignes = [i for i in indicateurs if i["valeur"] is not None]
    if not lignes:
        return None
    d = Drawing(largeur, 70 * mm)
    g = VerticalBarChart()
    g.x, g.y, g.width, g.height = 12 * mm, 20 * mm, largeur - 16 * mm, 42 * mm
    series = [[i["valeur"] for i in lignes]]
    if any(i["precedent"] is not None for i in lignes):
        series.insert(0, [i["precedent"] or 0 for i in lignes])
    g.data = series
    noms = {"Taux d'exécution budgétaire": "Exécution", "Taux d'autonomie financière": "Autonomie",
            "Dépendance à la subvention": "Dépendance", "Poids de la masse salariale": "Masse salariale",
            "Taux de féminisation": "Féminisation", "Taux de réalisation des objectifs": "Objectifs"}
    g.categoryAxis.categoryNames = [noms.get(i["libelle"], _court(i["libelle"], 16)).encode("cp1252", "replace")
                                    .decode("cp1252") for i in lignes]
    g.categoryAxis.labels.fontSize = 7.5
    g.categoryAxis.strokeColor = TRAIT
    g.valueAxis.valueMin = 0
    g.valueAxis.valueMax = max(100, max(max(s) for s in series))
    g.valueAxis.valueStep = 25
    g.valueAxis.labels.fontSize = 7
    g.valueAxis.strokeColor = TRAIT
    g.valueAxis.visibleGrid, g.valueAxis.gridStrokeColor = True, colors.HexColor("#e8ece9")
    g.barSpacing, g.groupSpacing = 2, 10
    g.bars[0].fillColor = GRIS if len(series) == 2 else MARQUE
    if len(series) == 2:
        g.bars[1].fillColor = MARQUE
    for i in range(len(series)):
        g.bars[i].strokeColor = None
    g.barLabelFormat = lambda v: _fmt(v)
    g.barLabels.fontSize, g.barLabels.nudge = 6.5, 6
    d.add(g)
    # Légende
    x = 12 * mm
    for libelle, couleur in ([(str(annee_prec), GRIS)] if len(series) == 2 else []) + [(str(annee), MARQUE)]:
        from reportlab.graphics.shapes import Rect

        d.add(Rect(x, 6 * mm, 7, 7, fillColor=couleur, strokeColor=None))
        d.add(String(x + 10, 6 * mm + 1, f"Exercice {libelle}", fontSize=7.5, fillColor=DISCRET))
        x += 34 * mm
    return d


# --- Mise en page ----------------------------------------------------------------------------------------------------

def _styles_rapport():
    s = _styles()
    s["h1"] = ParagraphStyle("h1", parent=s["rubrique"], fontSize=14, textColor=VERT, spaceBefore=4, spaceAfter=8)
    s["h2"] = ParagraphStyle("h2", parent=s["rubrique"], fontSize=11, spaceBefore=10, spaceAfter=4)
    s["puce"] = ParagraphStyle("puce", parent=s["texte"], leftIndent=10, bulletIndent=0, spaceAfter=3)
    s["note"] = ParagraphStyle("note", parent=s["texte"], fontSize=7.5, leading=9.5, textColor=DISCRET)
    s["grand"] = ParagraphStyle("grand", parent=s["titre"], fontSize=24, leading=29, spaceBefore=30, spaceAfter=8)
    s["entete"] = ParagraphStyle("entete", parent=s["cellule"], fontName="Helvetica-Bold", textColor=colors.white)
    s["droite"] = ParagraphStyle("droite", parent=s["cellule"], alignment=2)
    s["ia"] = ParagraphStyle("ia", parent=s["texte"], fontSize=9.5, leading=13.5, spaceAfter=5)
    return s


def _tableau(lignes, largeurs, s, droite_a_partir_de=1):
    entete = [Paragraph(_t(x), s["entete"]) for x in lignes[0]]
    corps = [[Paragraph(_t(x), s["droite"] if j >= droite_a_partir_de else s["cellule"]) for j, x in enumerate(l)]
             for l in lignes[1:]]
    t = Table([entete] + corps, colWidths=largeurs, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), VERT), ("LINEBELOW", (0, 1), (-1, -1), 0.3, TRAIT),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, FOND]), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]))
    return t


def _puces(items, s, style="puce"):
    return [Paragraph(_t(x), s[style], bulletText="•") for x in items if x]


def generer(d, synthese_ia=None):
    """PDF du rapport annuel. `synthese_ia` : dict produit par assistant.synthese_rapport (facultatif)."""
    p = Parametres.charger()
    s = _styles_rapport()
    c = d["campagne"]
    tampon = BytesIO()
    genere = timezone.localtime().strftime("%d/%m/%Y à %H:%M")
    doc = SimpleDocTemplate(tampon, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm,
                            bottomMargin=18 * mm, title=f"Rapport annuel – {c.nom}", author=p.valeur("institution"))
    perimetre = ", ".join(d["perimetre"]) if d["perimetre"] else "tous les établissements"
    base = BASES_LIBELLES.get(d["base"], d["base"])
    e = []

    # Couverture
    if p.logo:
        try:
            e.append(Image(p.logo.path, width=24 * mm, height=24 * mm, kind="proportional"))
        except Exception:  # logo illisible : le rapport reste produit
            pass
    e += [Paragraph(_t(p.valeur("pays")).upper(), s["pays"]), Paragraph(_t(p.valeur("devise")), s["devise"]),
          Spacer(1, 3), Paragraph(_t(p.valeur("ministere")), s["sous"]), Paragraph(_t(p.valeur("institution")), s["sous"]),
          Spacer(1, 40), Paragraph(_t("Rapport annuel sur la situation des établissements publics nationaux"), s["grand"]),
          Paragraph(_t(f"Exercice {c.exercice} · {c.nom}"), s["sous"]), Spacer(1, 26)]
    part = d["participation"]
    chiffres = [("Établissements interrogés", str(part["invites"])), ("Réponses transmises", str(part["soumis"])),
                ("Taux de réponse", f"{part['taux']} %"), ("Réponses validées", str(part["valides"]))]
    t = Table([[Paragraph(f"<font size=20 color='#007a4d'><b>{_t(v)}</b></font>", s["texte"]) for _, v in chiffres],
               [Paragraph(_t(k), s["note"]) for k, _ in chiffres]], colWidths=[43 * mm] * 4)
    t.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.5, TRAIT), ("INNERGRID", (0, 0), (-1, -1), 0.5, TRAIT),
                           ("BACKGROUND", (0, 0), (-1, -1), FOND), ("TOPPADDING", (0, 0), (-1, -1), 8),
                           ("BOTTOMPADDING", (0, 0), (-1, -1), 6), ("LEFTPADDING", (0, 0), (-1, -1), 8)]))
    e += [t, Spacer(1, 30), Paragraph(_t(f"Périmètre : {perimetre}. Statistiques calculées sur les {base} "
                                         f"(n = {len(d['reponses'])})."), s["sous"]),
          Paragraph(_t(f"Document généré automatiquement par ENQUÊTE-EPN le {genere}."), s["sous"]), PageBreak()]

    # 1. Synthèse
    e.append(Paragraph(_t("1. Synthèse"), s["h1"]))
    if synthese_ia and synthese_ia.get("synthese"):
        for para in str(synthese_ia["synthese"]).split("\n"):
            if para.strip():
                e.append(Paragraph(_t(para.strip()), s["ia"]))
        for titre, cle in (("Points forts", "points_forts"), ("Points de vigilance", "points_vigilance"),
                           ("Besoins exprimés par les établissements", "besoins"), ("Recommandations", "recommandations")):
            if synthese_ia.get(cle):
                e += [Paragraph(_t(titre), s["h2"])] + _puces(synthese_ia[cle], s)
        e += [Spacer(1, 4), Paragraph(_t("Synthèse rédigée avec l'assistant IA à partir des données agrégées du rapport, "
                                         "relue sous la responsabilité de l'équipe d'enquête."), s["note"]),
              Paragraph(_t("Constats chiffrés"), s["h2"])]
    e += _puces(constats(d), s)

    # 2. Participation
    e += [CondPageBreak(90 * mm), Paragraph(_t("2. Participation à l'enquête"), s["h1"])]
    if part["par_tutelle"]:
        e += [Paragraph(_t("Taux de réponse par tutelle"), s["h2"]),
              _barres_horizontales(part["par_tutelle"], "libelle", "taux")]
    for titre, cle in (("Par catégorie d'établissement", "par_categorie"), ("Par région", "par_region")):
        if part[cle]:
            lignes = [["", "Réponses transmises", "Établissements", "Taux"]] + [
                [l["libelle"], str(l["soumis"]), str(l["total"]), f"{l['taux']} %"] for l in part[cle]]
            e += [KeepTogether([Paragraph(_t(titre), s["h2"]), _tableau(lignes, [80 * mm, 32 * mm, 32 * mm, 30 * mm], s)])]
    if part["statuts"]:
        e += [KeepTogether([Paragraph(_t("Avancement des réponses"), s["h2"]), _tableau(
            [["Statut", "Nombre"]] + [[k, str(v)] for k, v in part["statuts"]], [120 * mm, 54 * mm], s)])]

    # 3. Indicateurs
    annee_prec = d["precedente"].exercice if d["precedente"] else None
    e += [CondPageBreak(110 * mm), Paragraph(_t("3. Indicateurs clés"), s["h1"])]
    graphique = _barres_comparees(d["indicateurs"], c.exercice, annee_prec)
    if graphique:
        e.append(graphique)
    entete = ["Indicateur", f"Exercice {c.exercice}"] + ([f"Exercice {annee_prec}", "Évolution"] if annee_prec else [])
    lignes = [entete] + [[i["libelle"], _fmt(i["valeur"], 1, " %")] + (
        [_fmt(i["precedent"], 1, " %"), _variation(i["valeur"], i["precedent"])] if annee_prec else [])
        for i in d["indicateurs"]]
    e += [_tableau(lignes, [74 * mm, 34 * mm, 34 * mm, 32 * mm] if annee_prec else [110 * mm, 64 * mm], s),
          Spacer(1, 3), Paragraph(_t("Formules : " + " ; ".join(f"{i['libelle']} = {i['formule']}"
                                                                for i in d["indicateurs"]) + "."), s["note"])]

    # 4. Statistiques par rubrique
    e += [PageBreak(), Paragraph(_t("4. Résultats par rubrique"), s["h1"])]
    for b in d["blocs"]:
        num = [i for i in b["questions"] if i["genre"] == "numerique" and i["stats"].get("n")]
        freq = [i for i in b["questions"] if i["genre"] == "frequence" and i["stats"].get("n")]
        if not num and not freq:
            continue
        titre = Paragraph(_t(f"{b['module']['code']}. {b['module']['titre']}"), s["h2"])
        if num:
            entete = ["Question", "n", "Total", "Moyenne", "Médiane"] + (["Moy. N-1"] if annee_prec else [])
            lignes = [entete]
            for i in num:
                st = i["stats"]
                unite = " %" if i["q"]["type"] == "pourcentage" else ""
                l = [f"{i['q']['code']} · {i['q']['libelle']}", str(st["n"]),
                     "—" if i["q"]["type"] == "pourcentage" else _fmt(st["somme"]), _fmt(st["moyenne"], 0, unite),
                     _fmt(st["mediane"], 0, unite)]
                if annee_prec:
                    l.append(_fmt((i.get("precedent") or {}).get("moyenne"), 0, unite))
                lignes.append(l)
            largeurs = ([52 * mm, 9 * mm, 35 * mm, 26 * mm, 26 * mm, 26 * mm] if annee_prec
                        else [64 * mm, 9 * mm, 39 * mm, 31 * mm, 31 * mm])
            tableau = _tableau(lignes, largeurs, s)
            e.append(KeepTogether([titre, tableau]) if len(num) < 12 else titre)
            if len(num) >= 12:
                e.append(tableau)
            titre = None
        for i in freq:
            st = i["stats"]
            lignes = st["lignes"] if i["q"]["type"] == "echelle" else sorted(st["lignes"], key=lambda l: -l["effectif"])
            e.append(KeepTogether(([titre] if titre else []) + [
                Paragraph(_t(f"{i['q']['code']} · {i['q']['libelle']} (n = {st['n']})"), s["cellule"]), Spacer(1, 2),
                _barres_horizontales(lignes, "libelle", "pourcentage"), Spacer(1, 4)]))
            titre = None

    # 5. Contrôle qualité
    e += [CondPageBreak(60 * mm), Paragraph(_t("5. Contrôle qualité des données"), s["h1"])]
    if d["atypiques"]:
        par_q = Counter((a["code"], a["libelle"]) for a in d["atypiques"])
        e += [Paragraph(_t("Valeurs très éloignées de celles des autres établissements (hors de l'intervalle "
                           "[Q1 - 3 × écart interquartile ; Q3 + 3 × écart interquartile]). Le détail par établissement "
                           "est consultable dans l'application, page Statistiques."), s["texte"]), Spacer(1, 4),
              _tableau([["Question", "Valeurs atypiques"]] + [[f"{k[0]} · {k[1]}", str(v)] for k, v in par_q.most_common()],
                       [140 * mm, 34 * mm], s)]
    else:
        e.append(Paragraph(_t("Aucune valeur atypique détectée (calcul effectué à partir de 5 réponses par question)."),
                           s["texte"]))

    # Méthodologie
    e += [Spacer(1, 10), Paragraph(_t("Méthodologie"), s["h2"]), Paragraph(_t(
        f"Les statistiques portent sur les {base} de la campagne « {c.nom} » (exercice {c.exercice}), périmètre : "
        f"{perimetre}. Le taux de réponse rapporte les réponses transmises (envoyées, en revue ou validées) au nombre "
        "d'établissements interrogés. Les indicateurs sont des ratios de totaux (et non des moyennes de ratios). "
        + (f"La comparaison porte sur la campagne de l'exercice {annee_prec}, sur la même base. " if annee_prec else
           "Aucune campagne antérieure n'est disponible pour la comparaison. ")
        + "Aucune donnée nominative (répondant, coordonnées) ne figure dans ce rapport."), s["texte"])]

    mention = f"{p.valeur('institution')} · Rapport annuel {c.exercice} · généré le {genere}"
    doc.build(e, onFirstPage=lambda cv, dc: _pied(cv, dc, mention), onLaterPages=lambda cv, dc: _pied(cv, dc, mention))
    return tampon.getvalue()


def nom_fichier(campagne):
    return f"Rapport_annuel_EPN_{campagne.exercice}.pdf"

