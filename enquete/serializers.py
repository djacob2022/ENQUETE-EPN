"""Conversion des objets en dictionnaires JSON pour l'interface React."""
from django.urls import reverse

from .pieces import ACCEPT, TAILLE_MAX
from .questionnaire import CHAMPS_TRADUITS, TYPES, TYPES_NUMERIQUES, affichage, oui_non
from .services import etat, reponse_precedente


def _date(d):
    return d.isoformat() if d else None


def _en(objet, cle):
    """Version anglaise affichée dans l'éditeur : celle saisie, sinon la traduction automatique du texte par défaut."""
    from .questionnaire_en import EN

    return objet.get(f"{cle}_en") or EN.get(objet.get(cle) or "", "")


def question(q, editeur=False):
    item = {k: q[k] for k in ("code", "libelle", "type")}
    item["obligatoire"] = q.get("obligatoire", True)
    for cle in ("min", "max", "unite", "aide", "annee", "si", "colonnes", "libelle_min", "libelle_max"):
        if cle in q:
            item[cle] = q[cle]
    if q["type"] == "oui_non":
        item["choix"] = [{"valeur": v, "libelle": l} for v, l in oui_non()]
    elif "choix" in q:
        item["choix"] = [{"valeur": v, "libelle": l} for v, l in q["choix"]]
    if editeur:  # F-16 : champs de la version anglaise
        for cle in CHAMPS_TRADUITS:
            if q.get(cle):
                item[f"{cle}_en"] = _en(q, cle)
        if q["type"] != "oui_non" and "choix" in item:
            from .questionnaire_en import EN

            traduits = q.get("choix_en") or {}
            for c in item["choix"]:
                c["libelle_en"] = traduits.get(c["valeur"]) or EN.get(c["libelle"], "")
        if "colonnes" in item:
            item["colonnes"] = [c | {"libelle_en": _en(c, "libelle")} for c in item["colonnes"]]
    return item


def questionnaire(campagne_obj, tous=False):
    """Questionnaire d'une campagne. `tous` : modules désactivés compris (éditeur)."""
    q = campagne_obj.q
    modules = [{"code": m["code"], "titre": m["titre"], "intro": m.get("intro", ""), "actif": m.get("actif", True),
                "questions": [question(x, editeur=tous) for x in m["questions"]]}
               | ({"titre_en": _en(m, "titre"), "intro_en": _en(m, "intro")} if tous else {})
               for m in (q.tous_les_modules if tous else q.modules)]
    sortie = {"modules": modules, "version": q.version, "fichiers": {"accept": ACCEPT, "taille_max": TAILLE_MAX}}
    if tous:
        sortie |= {"regles": q.regles, "types": [{"valeur": k, "libelle": v} for k, v in TYPES.items()],
                   "modifie_le": q.definition.get("modifie_le"), "modifie_par": q.definition.get("modifie_par", "")}
    return sortie


def campagne(c):
    if c is None:
        return None
    return {"id": c.pk, "nom": c.nom, "exercice": c.exercice, "date_ouverture": _date(c.date_ouverture),
            "date_cloture": _date(c.date_cloture), "active": c.active, "ouverte": c.est_ouverte,
            "cible_tutelles": c.cible_tutelles, "cible_categories": c.cible_categories,
            "relances_auto": c.relances_auto, "version_questionnaire": c.q.version}


def epn(e):
    return {"id": e.pk, "nom": e.nom, "sigle": e.sigle, "categorie": e.categorie, "tutelle": e.tutelle,
            "region": e.region, "secteur": e.secteur, "email_contact": e.email_contact, "actif": e.actif,
            "etat": e.etat, "etat_libelle": e.get_etat_display()}


def piece_publique(p):
    return {"code": p.code, "nom": p.nom_original, "taille": p.taille, "date_depot": _date(p.date_depot),
            "url": reverse("api:piece_publique", args=[p.reponse.jeton, p.code])}


def piece_admin(p):
    return {"id": p.pk, "code": p.code, "nom": p.nom_original, "taille": p.taille, "date_depot": _date(p.date_depot),
            "url": reverse("api:piece_admin", args=[p.pk])}


def identification(r):
    return {"nom": r.nom, "prenom": r.prenom, "fonction": r.fonction, "email": r.email or r.epn.email_contact,
            "telephone": r.telephone}


def reponse_publique(r):
    """Tout ce dont le formulaire a besoin, pour le détenteur du lien personnel."""
    return {
        "etat": etat(r),
        "statut": r.statut,
        "langue": r.langue,
        "epn": {"nom": r.epn.nom, "sigle": r.epn.sigle, "categorie": r.epn.categorie, "tutelle": r.epn.tutelle},
        "campagne": campagne(r.campagne),
        "identification": identification(r),
        "identifie": bool(r.nom),
        "donnees": r.donnees,
        "modules_completes": r.modules_completes,
        "avancement": r.avancement(),
        "pieces": {p.code: piece_publique(p) for p in r.pieces.all()},
        "date_soumission": _date(r.date_soumission),
        "date_modification": _date(r.date_modification),
        "date_limite": _date(r.date_limite_effective),
        "commentaires": r.commentaires if r.statut == "a_corriger" else {},
        "precedente": precedente.campagne.exercice if (precedente := reponse_precedente(r)) else None,
    }


def reponse_resume(r):
    return {
        "id": r.pk, "statut": r.statut, "statut_libelle": r.get_statut_display(), "avancement": r.avancement(),
        "epn": epn(r.epn), "repondant": r.repondant, "email": r.email, "telephone": r.telephone,
        "fonction": r.fonction, "date_invitation": _date(r.date_invitation),
        "date_soumission": _date(r.date_soumission), "date_modification": _date(r.date_modification),
        "nombre_relances": r.nombre_relances, "date_derniere_relance": _date(r.date_derniere_relance),
        "lien": r.lien, "date_validation": _date(r.date_validation), "valide_par": r.valide_par,
        "date_limite": _date(r.date_limite), "a_des_commentaires": bool(r.commentaires),
    }


def anonymiser(resume):
    """Version sans données nominatives (rôle « lecteur ») : ni répondant ni coordonnées ni lien."""
    return resume | {"repondant": "", "email": "", "telephone": "", "fonction": "", "lien": ""}


def reponse_detail(r):
    pieces = {p.code: piece_admin(p) for p in r.pieces.all()}
    precedente = reponse_precedente(r)
    from .statistiques import bornes_atypiques

    bornes = bornes_atypiques(r.campagne.q, list(r.campagne.reponses.filter(statut__in=("soumis", "en_revue", "valide"))))
    modules = []
    for m in r.campagne.q.modules:
        lignes = []
        for q in m["questions"]:
            ligne = {"code": q["code"], "libelle": q["libelle"], "type": q["type"],
                     "valeur": affichage(q, r.donnees.get(q["code"])), "piece": pieces.get(q["code"])}
            # Détection d'anomalies (F-32) : écart de plus de 50 % avec la réponse de l'année précédente.
            v, ancien = r.donnees.get(q["code"]), precedente.donnees.get(q["code"]) if precedente else None
            if q["type"] in TYPES_NUMERIQUES and not q.get("annee") and isinstance(ancien, (int, float)):
                ligne["precedent"] = affichage(q, ancien)
                if isinstance(v, (int, float)) and ancien:
                    ecart = 100 * (v - ancien) / abs(ancien)
                    ligne["ecart"] = round(ecart)
                    ligne["anomalie"] = abs(ecart) > 50
            # Valeur atypique au sein de la campagne (F-32), par rapport aux autres établissements.
            if q["code"] in bornes and isinstance(v, (int, float)) and not isinstance(v, bool):
                bas, haut = bornes[q["code"]]
                if not bas <= v <= haut:
                    ligne["atypique"] = "haut" if v > haut else "bas"
            lignes.append(ligne)
        modules.append({"code": m["code"], "titre": m["titre"], "complet": m["code"] in r.modules_completes,
                        "lignes": lignes})
    return reponse_resume(r) | {
        "campagne": campagne(r.campagne),
        "commentaires": r.commentaires,
        "exercice_precedent": precedente.campagne.exercice if precedente else None,
        "export_url": reverse("api:reponse_export", args=[r.pk]),
        "pdf_url": reverse("api:reponse_pdf", args=[r.pk]),
        "modules": modules,
        "pieces": list(pieces.values()),
        "zip_url": reverse("api:pieces_zip", args=[r.pk]) if pieces else None,
        "envois": [{"type": e.get_type_display(), "date": _date(e.date), "succes": e.succes,
                    "destinataires": e.destinataires, "par": e.par} for e in r.envois.all()[:30]],
    }
