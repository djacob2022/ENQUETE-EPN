"""Contrôle et enregistrement d'un questionnaire modifié dans l'éditeur (F-10 à F-14).

Le navigateur envoie la définition complète ; elle est normalisée ici (champs connus seulement), puis contrôlée :
codes uniques et stables, types connus, choix renseignés, conditions et règles qui visent des questions existantes.
Une question qui a déjà reçu des réponses ne peut être ni supprimée ni changée de type : l'historique reste lisible.
"""
import re

from django.db import transaction
from django.utils import timezone

from .questionnaire import TYPES, TYPES_A_CHOIX, TYPES_NUMERIQUES
from .services import Refus, recalculer_completude

CODE_MODULE = re.compile(r"^[A-Z]{1,2}$")
CODE_QUESTION = re.compile(r"^[A-Z]{1,2}\d{2,3}$")


def _texte(v, longueur):
    return str(v or "").strip()[:longueur]


def _nombre(v):
    if v in (None, ""):
        return None
    try:
        n = float(str(v).replace(",", "."))
    except ValueError:
        raise Refus(f"« {v} » n'est pas un nombre.")
    return int(n) if n.is_integer() else n


def _choix(brut, q_code):
    choix, vus = [], set()
    for c in brut or []:
        valeur, libelle = (c.get("valeur"), c.get("libelle")) if isinstance(c, dict) else (c[0], c[1])
        libelle = _texte(libelle, 200)
        valeur = _texte(valeur, 40) or re.sub(r"[^a-z0-9]+", "_", libelle.lower()).strip("_")[:40]
        if not libelle:
            continue
        if valeur in vus:
            raise Refus(f"{q_code} : deux choix portent la même valeur « {valeur} ».")
        vus.add(valeur)
        choix.append([valeur, libelle])
    return choix


def _prochain_code(module_code, utilises):
    n = 1
    while f"{module_code}{n:02d}" in utilises:
        n += 1
    return f"{module_code}{n:02d}"


def normaliser(definition, ancienne):
    """Renvoie une définition propre, ou lève Refus avec un message lisible."""
    if not isinstance(definition, dict) or not isinstance(definition.get("modules"), list):
        raise Refus("Questionnaire illisible.")
    codes_existants = {q["code"] for m in ancienne.get("modules", []) for q in m.get("questions", [])}
    utilises = set(codes_existants)
    modules, codes_modules, toutes = [], set(), {}

    for m in definition["modules"]:
        code_m = _texte(m.get("code"), 2).upper()
        if not CODE_MODULE.match(code_m):
            raise Refus(f"Code de module invalide « {code_m} » : une ou deux lettres majuscules.")
        if code_m in codes_modules:
            raise Refus(f"Deux modules portent le code {code_m}.")
        codes_modules.add(code_m)
        titre = _texte(m.get("titre"), 200)
        if not titre:
            raise Refus(f"Le module {code_m} n'a pas de titre.")
        questions = []
        for q in m.get("questions") or []:
            code = _texte(q.get("code"), 6).upper()
            if not code:
                code = _prochain_code(code_m, utilises)
            if not CODE_QUESTION.match(code):
                raise Refus(f"Code de question invalide « {code} ».")
            if code in toutes:
                raise Refus(f"Deux questions portent le code {code}.")
            utilises.add(code)
            type_q = q.get("type")
            if type_q not in TYPES:
                raise Refus(f"{code} : type de question inconnu.")
            libelle = _texte(q.get("libelle"), 500)
            if not libelle:
                raise Refus(f"{code} : le libellé est vide.")
            propre = {"code": code, "libelle": libelle, "type": type_q}
            if q.get("obligatoire") is False:
                propre["obligatoire"] = False
            for cle, longueur in (("aide", 500), ("unite", 40), ("libelle_min", 60), ("libelle_max", 60)):
                if _texte(q.get(cle), longueur):
                    propre[cle] = _texte(q.get(cle), longueur)
            if type_q in TYPES_NUMERIQUES or type_q == "echelle":
                for cle in ("min", "max"):
                    n = _nombre(q.get(cle))
                    if n is not None:
                        propre[cle] = n
                if "min" in propre and "max" in propre and propre["min"] > propre["max"]:
                    raise Refus(f"{code} : le minimum dépasse le maximum.")
            if type_q == "echelle":
                propre.setdefault("min", 1)
                propre.setdefault("max", 5)
                if not (0 <= propre["min"] < propre["max"] <= 10):
                    raise Refus(f"{code} : l'échelle va de 0 à 10 au plus.")
            if q.get("annee"):
                propre["annee"] = True
            if type_q in TYPES_A_CHOIX:
                propre["choix"] = _choix(q.get("choix"), code)
                if len(propre["choix"]) < 2:
                    raise Refus(f"{code} : indiquez au moins deux choix.")
            if type_q == "tableau":
                colonnes = []
                for c in q.get("colonnes") or []:
                    lib = _texte(c.get("libelle"), 80)
                    if lib:
                        cc = _texte(c.get("code"), 30) or re.sub(r"[^a-z0-9]+", "_", lib.lower()).strip("_")[:30]
                        colonnes.append({"code": cc, "libelle": lib, "type": "nombre" if c.get("type") == "nombre" else "texte"})
                if not colonnes:
                    raise Refus(f"{code} : un tableau doit avoir au moins une colonne.")
                propre["colonnes"] = colonnes
            si = q.get("si") or {}
            if si.get("question"):
                propre["si"] = {"question": _texte(si["question"], 6).upper(),
                                "valeurs": [_texte(v, 40) for v in si.get("valeurs") or [] if _texte(v, 40)]}
            toutes[code] = propre
            questions.append(propre)
        modules.append({"code": code_m, "titre": titre, "intro": _texte(m.get("intro"), 1000),
                        "actif": m.get("actif", True) is not False, "questions": questions})

    for q in toutes.values():
        si = q.get("si")
        if si:
            cible = toutes.get(si["question"])
            if cible is None or si["question"] == q["code"]:
                raise Refus(f"{q['code']} : la condition d'affichage vise une question inconnue ({si['question']}).")
            if cible["type"] not in ("oui_non", "choix", "choix_multiple") or not si["valeurs"]:
                raise Refus(f"{q['code']} : la condition doit porter sur une question à choix, avec au moins une valeur.")

    regles = []
    for r in definition.get("regles") or []:
        if r.get("type") == "somme":
            total, parties = _texte(r.get("total"), 6).upper(), [_texte(p, 6).upper() for p in r.get("parties") or []]
            codes = [total, *parties]
            propre = {"type": "somme", "total": total, "parties": parties}
            if len(parties) < 2:
                raise Refus("Une règle de somme compte au moins deux parties.")
        elif r.get("type") == "inferieur":
            codes = [_texte(r.get("petit"), 6).upper(), _texte(r.get("grand"), 6).upper()]
            propre = {"type": "inferieur", "petit": codes[0], "grand": codes[1]}
        else:
            raise Refus("Type de règle inconnu.")
        for c in codes:
            if c not in toutes or toutes[c]["type"] not in TYPES_NUMERIQUES:
                raise Refus(f"La règle vise {c}, qui n'est pas une question numérique du questionnaire.")
        if _texte(r.get("message"), 300):
            propre["message"] = _texte(r.get("message"), 300)
        regles.append(propre)

    return {"modules": modules, "regles": regles}, toutes, codes_existants


def enregistrer(campagne, definition, par):
    """Contrôle la définition, refuse ce qui casserait des réponses existantes, puis l'enregistre (version + 1)."""
    ancienne = campagne.questionnaire or {}
    propre, toutes, codes_existants = normaliser(definition, ancienne)
    anciennes_q = {q["code"]: q for m in ancienne.get("modules", []) for q in m.get("questions", [])}

    reponses = list(campagne.reponses.exclude(donnees={}))
    avec_donnees = {c for r in reponses for c, v in r.donnees.items() if v not in (None, "", [])}
    for code in codes_existants - set(toutes):
        if code in avec_donnees:
            raise Refus(f"La question {code} a déjà reçu des réponses : désactivez son module ou rendez-la "
                        f"facultative plutôt que de la supprimer.")
    for code, q in toutes.items():
        ancien = anciennes_q.get(code)
        if ancien and ancien["type"] != q["type"] and code in avec_donnees:
            raise Refus(f"La question {code} a déjà reçu des réponses : son type ne peut plus changer.")

    propre["version"] = int(ancienne.get("version", 1)) + 1
    propre["modifie_le"] = timezone.now().isoformat()
    propre["modifie_par"] = par
    with transaction.atomic():
        campagne.questionnaire = propre
        campagne.save(update_fields=["questionnaire"])
        # La complétude des réponses en cours suit le nouveau questionnaire (question ajoutée, rendue obligatoire…).
        for r in campagne.reponses.exclude(statut__in=("soumis", "en_revue", "valide")).select_related("campagne"):
            r.campagne = campagne
            recalculer_completude(r)
            r.save(update_fields=["modules_completes"])
    return propre
