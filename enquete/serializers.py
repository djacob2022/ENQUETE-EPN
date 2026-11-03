"""Conversion des objets en dictionnaires JSON pour l'interface React."""
from django.urls import reverse

from .pieces import ACCEPT, TAILLE_MAX
from .questionnaire import MODULES, OUI_NON, affichage
from .services import etat


def _date(d):
    return d.isoformat() if d else None


def questionnaire():
    modules = []
    for m in MODULES:
        questions = []
        for q in m["questions"]:
            item = {k: q[k] for k in ("code", "libelle", "type") }
            item["obligatoire"] = q.get("obligatoire", True)
            for cle in ("min", "max", "unite", "aide", "annee"):
                if cle in q:
                    item[cle] = q[cle]
            if q["type"] == "oui_non":
                item["choix"] = [{"valeur": v, "libelle": l} for v, l in OUI_NON]
            elif "choix" in q:
                item["choix"] = [{"valeur": v, "libelle": l} for v, l in q["choix"]]
            questions.append(item)
        modules.append({"code": m["code"], "titre": m["titre"], "intro": m.get("intro", ""), "questions": questions})
    return {"modules": modules, "fichiers": {"accept": ACCEPT, "taille_max": TAILLE_MAX}}


def campagne(c):
    if c is None:
        return None
    return {"id": c.pk, "nom": c.nom, "exercice": c.exercice, "date_ouverture": _date(c.date_ouverture),
            "date_cloture": _date(c.date_cloture), "active": c.active, "ouverte": c.est_ouverte}


def epn(e):
    return {"id": e.pk, "nom": e.nom, "sigle": e.sigle, "categorie": e.categorie, "tutelle": e.tutelle,
            "region": e.region, "email_contact": e.email_contact, "actif": e.actif}


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
    }


def reponse_resume(r):
    return {
        "id": r.pk, "statut": r.statut, "statut_libelle": r.get_statut_display(), "avancement": r.avancement(),
        "epn": epn(r.epn), "repondant": r.repondant, "email": r.email, "telephone": r.telephone,
        "fonction": r.fonction, "date_invitation": _date(r.date_invitation),
        "date_soumission": _date(r.date_soumission), "date_modification": _date(r.date_modification),
        "nombre_relances": r.nombre_relances, "date_derniere_relance": _date(r.date_derniere_relance),
        "lien": r.lien,
    }


def reponse_detail(r):
    pieces = {p.code: piece_admin(p) for p in r.pieces.all()}
    modules = []
    for m in MODULES:
        modules.append({
            "code": m["code"], "titre": m["titre"], "complet": m["code"] in r.modules_completes,
            "lignes": [{"code": q["code"], "libelle": q["libelle"], "type": q["type"],
                        "valeur": affichage(q, r.donnees.get(q["code"])), "piece": pieces.get(q["code"])}
                       for q in m["questions"]],
        })
    return reponse_resume(r) | {
        "campagne": campagne(r.campagne),
        "modules": modules,
        "pieces": list(pieces.values()),
        "zip_url": reverse("api:pieces_zip", args=[r.pk]) if pieces else None,
        "envois": [{"type": e.get_type_display(), "date": _date(e.date), "succes": e.succes,
                    "destinataires": e.destinataires, "par": e.par} for e in r.envois.all()[:30]],
    }
