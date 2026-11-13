"""Calculs statistiques sur les réponses (descriptifs, fréquences, indicateurs)."""
import statistics
from collections import Counter, defaultdict

from .questionnaire import oui_non, TYPES_NUMERIQUES


def descriptifs(valeurs):
    valeurs = [v for v in valeurs if isinstance(v, (int, float))]
    if not valeurs:
        return {"n": 0}
    return {
        "n": len(valeurs),
        "somme": sum(valeurs),
        "moyenne": statistics.fmean(valeurs),
        "mediane": statistics.median(valeurs),
        "min": min(valeurs),
        "max": max(valeurs),
        "ecart_type": statistics.stdev(valeurs) if len(valeurs) > 1 else 0,
        **dict(zip(("q1", "q3"), _quartiles(valeurs))),
    }


def _quartiles(valeurs):
    """Premier et troisième quartiles (méthode inclusive, comme QUARTILE.INCLUS d'Excel : recalculable)."""
    if len(valeurs) < 2:
        return valeurs[0], valeurs[0]
    q = statistics.quantiles(valeurs, n=4, method="inclusive")
    return q[0], q[2]


def histogramme(valeurs, classes=6):
    """Répartition des valeurs numériques en classes de même largeur (F-39)."""
    valeurs = [v for v in valeurs if isinstance(v, (int, float))]
    if len(valeurs) < 2 or min(valeurs) == max(valeurs):
        return []
    bas, haut = min(valeurs), max(valeurs)
    largeur = (haut - bas) / classes
    effectifs = [0] * classes
    for v in valeurs:
        effectifs[min(int((v - bas) / largeur), classes - 1)] += 1
    return [{"de": bas + i * largeur, "a": bas + (i + 1) * largeur, "effectif": e} for i, e in enumerate(effectifs)]


def choix_de(q):
    if q["type"] == "oui_non":
        return oui_non()
    if q["type"] == "echelle":
        return [[v, str(v)] for v in range(int(q.get("min", 1)), int(q.get("max", 5)) + 1)]
    return q.get("choix", [])


def frequences(q, valeurs):
    compteur = Counter()
    n = 0
    for v in valeurs:
        if v in (None, "", []):
            continue
        n += 1
        if isinstance(v, list):
            compteur.update(v)
        else:
            compteur[v] += 1
    choix = choix_de(q)
    lignes = [{"code": c, "libelle": lib, "effectif": compteur.get(c, 0),
               "pourcentage": (100 * compteur.get(c, 0) / n) if n else 0} for c, lib in choix]
    return {"n": n, "lignes": lignes}


QUALITATIFS = ("choix", "choix_multiple", "oui_non", "echelle")


def par_question(questionnaire, reponses, precedentes=None):
    """Pour chaque question : statistiques descriptives (numérique) ou fréquences (choix), avec N-1 (F-40)."""
    resultats = []
    for module in questionnaire.modules:
        bloc = {"module": module, "questions": []}
        for q in module["questions"]:
            valeurs = [r.donnees.get(q["code"]) for r in reponses]
            if q.get("annee"):
                continue  # une somme ou une moyenne d'années n'a pas de sens
            if q["type"] in TYPES_NUMERIQUES:
                item = {"q": q, "genre": "numerique", "stats": descriptifs(valeurs) | {"histogramme": histogramme(valeurs)}}
                if precedentes:
                    item["precedent"] = descriptifs([r.donnees.get(q["code"]) for r in precedentes])
                bloc["questions"].append(item)
            elif q["type"] in QUALITATIFS:
                bloc["questions"].append({"q": q, "genre": "frequence", "stats": frequences(q, valeurs)})
        if bloc["questions"]:
            resultats.append(bloc)
    return resultats


def _ratio(num, den):
    return 100 * num / den if den else None


def indicateurs(reponses):
    """Indicateurs agrégés de la section 6.3 du cahier des charges (sur l'ensemble des réponses)."""
    def total(code):
        return sum(r.donnees.get(code) or 0 for r in reponses)

    return [
        {"libelle": "Taux d'exécution budgétaire", "valeur": _ratio(total("E02"), total("E01")),
         "formule": "Budget exécuté ÷ budget prévu"},
        {"libelle": "Taux d'autonomie financière", "valeur": _ratio(total("E04"), total("E03") + total("E04")),
         "formule": "Ressources propres ÷ (subvention + ressources propres)"},
        {"libelle": "Dépendance à la subvention", "valeur": _ratio(total("E03"), total("E03") + total("E04")),
         "formule": "Subvention ÷ (subvention + ressources propres)"},
        {"libelle": "Poids de la masse salariale", "valeur": _ratio(total("E05"), total("E05") + total("E06") + total("E07")),
         "formule": "Dépenses de personnel ÷ dépenses totales (personnel + fonctionnement + investissement)"},
        {"libelle": "Taux de féminisation", "valeur": _ratio(total("D02"), total("D01")),
         "formule": "Effectif féminin ÷ effectif total"},
        {"libelle": "Taux de réalisation des objectifs", "valeur": _ratio(total("G02"), total("G01")),
         "formule": "Indicateurs atteints ÷ indicateurs du contrat de performance"},
    ]


def taux_par_groupe(reponses_campagne, attribut):
    """Taux de réponse (soumis / invités) par tutelle, catégorie ou région."""
    groupes = defaultdict(lambda: [0, 0])  # [envoyées, ciblées]
    for r in reponses_campagne:
        cle = getattr(r.epn, attribut) or "Non renseigné"
        groupes[cle][1] += 1
        if r.est_soumise:
            groupes[cle][0] += 1
    lignes = [{"libelle": k, "soumis": s, "total": t, "taux": round(100 * s / t) if t else 0}
              for k, (s, t) in groupes.items()]
    return sorted(lignes, key=lambda l: -l["taux"])


ATTRIBUTS_EPN = {"tutelle": "Tutelle", "categorie": "Catégorie", "region": "Région", "secteur": "Secteur"}


def _modalites(reponses, cle, questionnaire):
    """(libellé de la variable, liste [(code, libellé)], fonction réponse -> liste de codes)."""
    if cle in ATTRIBUTS_EPN:
        valeurs = sorted({getattr(r.epn, cle) or "Non renseigné" for r in reponses})
        return ATTRIBUTS_EPN[cle], [[v, v] for v in valeurs], lambda r: [getattr(r.epn, cle) or "Non renseigné"]
    q = questionnaire.question(cle)
    if q is None or q["type"] not in QUALITATIFS:
        return None

    def codes(r):
        v = r.donnees.get(cle)
        if v in (None, "", []):
            return []
        return [str(x) for x in v] if isinstance(v, list) else [str(v)]
    return q["libelle"], [[str(c), l] for c, l in choix_de(q)], codes


def tableau_croise(questionnaire, reponses, ligne, colonne):
    """Tableau croisé (F-45) : effectifs et pourcentages en ligne, pour deux variables qualitatives."""
    a, b = _modalites(reponses, ligne, questionnaire), _modalites(reponses, colonne, questionnaire)
    if a is None or b is None:
        return None
    (lib_l, mod_l, f_l), (lib_c, mod_c, f_c) = a, b
    cellules = defaultdict(int)
    n = 0
    for r in reponses:
        x, y = f_l(r), f_c(r)
        if x and y:
            n += 1
            for i in x:
                for j in y:
                    cellules[(i, j)] += 1
    lignes = []
    for code_l, libelle_l in mod_l:
        effectifs = [cellules[(code_l, code_c)] for code_c, _ in mod_c]
        total = sum(effectifs)
        lignes.append({"libelle": libelle_l, "effectifs": effectifs, "total": total,
                       "pourcentages": [100 * e / total if total else 0 for e in effectifs]})
    return {"ligne": lib_l, "colonne": lib_c, "colonnes": [l for _, l in mod_c], "lignes": lignes, "n": n}


def variables_croisables(questionnaire):
    sortie = [{"valeur": k, "libelle": v, "groupe": "Établissement"} for k, v in ATTRIBUTS_EPN.items()]
    for m, q in questionnaire.questions():
        if q["type"] in QUALITATIFS:
            sortie.append({"valeur": q["code"], "libelle": f"{q['code']} · {q['libelle']}", "groupe": m["titre"]})
    return sortie


def bornes_atypiques(questionnaire, reponses, k=3.0, minimum=5):
    """Valeurs atypiques au sein d'une campagne (F-32) : hors de [Q1 − k·IQR ; Q3 + k·IQR] (règle de Tukey).

    Calculées seulement à partir de `minimum` réponses : en dessous, les quartiles ne veulent rien dire.
    """
    bornes = {}
    for _, q in questionnaire.questions():
        if q["type"] not in TYPES_NUMERIQUES or q.get("annee"):
            continue
        valeurs = sorted(v for r in reponses if isinstance(v := r.donnees.get(q["code"]), (int, float))
                         and not isinstance(v, bool))
        if len(valeurs) < minimum:
            continue
        q1, q3 = _quartiles(valeurs)
        ecart = q3 - q1
        if ecart > 0:
            bornes[q["code"]] = (q1 - k * ecart, q3 + k * ecart)
    return bornes


def valeurs_atypiques(questionnaire, reponses):
    bornes = bornes_atypiques(questionnaire, reponses)
    sortie = []
    for r in reponses:
        for code, (bas, haut) in bornes.items():
            v = r.donnees.get(code)
            if isinstance(v, (int, float)) and not isinstance(v, bool) and not bas <= v <= haut:
                q = questionnaire.question(code)
                sortie.append({"reponse": r.pk, "epn": r.epn.nom, "code": code, "libelle": q["libelle"], "valeur": v,
                               "bas": bas, "haut": haut, "sens": "haut" if v > haut else "bas"})
    return sorted(sortie, key=lambda x: (x["code"], x["epn"]))
