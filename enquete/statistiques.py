"""Calculs statistiques sur les réponses (descriptifs, fréquences, indicateurs)."""
import statistics
from collections import Counter, defaultdict

from .questionnaire import MODULES, TYPES_NUMERIQUES


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
    }


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
    choix = q["choix"] if "choix" in q else [("oui", "Oui"), ("non", "Non")]
    lignes = [{"code": c, "libelle": lib, "effectif": compteur.get(c, 0),
               "pourcentage": (100 * compteur.get(c, 0) / n) if n else 0} for c, lib in choix]
    return {"n": n, "lignes": lignes}


def par_question(reponses):
    """Pour chaque question : statistiques descriptives (numérique) ou fréquences (choix)."""
    resultats = []
    for module in MODULES:
        bloc = {"module": module, "questions": []}
        for q in module["questions"]:
            valeurs = [r.donnees.get(q["code"]) for r in reponses]
            if q.get("annee"):
                continue  # une somme ou une moyenne d'années n'a pas de sens
            if q["type"] in TYPES_NUMERIQUES:
                bloc["questions"].append({"q": q, "genre": "numerique", "stats": descriptifs(valeurs)})
            elif q["type"] in ("choix", "choix_multiple", "oui_non"):
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
        {"libelle": "Poids des dépenses de personnel", "valeur": _ratio(total("E05"), total("E05") + total("E06") + total("E07")),
         "formule": "Dépenses de personnel ÷ dépenses totales"},
        {"libelle": "Taux de féminisation", "valeur": _ratio(total("D02"), total("D01")),
         "formule": "Effectif féminin ÷ effectif total"},
        {"libelle": "Indicateurs de performance atteints", "valeur": _ratio(total("G02"), total("G01")),
         "formule": "Indicateurs atteints ÷ indicateurs suivis"},
    ]


def taux_par_groupe(reponses_campagne, attribut):
    """Taux de réponse (soumis / invités) par tutelle, catégorie ou région."""
    groupes = defaultdict(lambda: [0, 0])
    for r in reponses_campagne:
        cle = getattr(r.epn, attribut) or "Non renseigné"
        groupes[cle][1] += 1
        if r.est_soumise:
            groupes[cle][0] += 1
    lignes = [{"libelle": k, "soumis": s, "total": t, "taux": round(100 * s / t) if t else 0}
              for k, (s, t) in groupes.items()]
    return sorted(lignes, key=lambda l: -l["taux"])
