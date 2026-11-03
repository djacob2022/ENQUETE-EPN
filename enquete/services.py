"""Logique métier partagée par l'API : saisie du questionnaire, pièces jointes, soumission, filtres."""
import zipfile
from io import BytesIO

from django.db import transaction
from django.db.models import Count, Q
from django.http import QueryDict
from django.utils import timezone
from django.utils.text import get_valid_filename

from .emails import envoyer_accuse
from .forms import ModuleForm
from .models import Campagne, PieceJointe, Reponse
from .pieces import valider_piece
from .questionnaire import MODULES


class Refus(Exception):
    """Action impossible dans l'état actuel (message destiné à l'utilisateur)."""

    def __init__(self, message, statut=400):
        super().__init__(message)
        self.message = message
        self.statut = statut


def module_par_code(code):
    for m in MODULES:
        if m["code"] == code:
            return m
    raise Refus("Rubrique inconnue.", 404)


def etat(reponse):
    if reponse.est_soumise:
        return "soumis"
    if not reponse.campagne.active or not reponse.campagne.est_ouverte:
        return "ferme"
    return "ouvert"


def exiger_saisie_possible(reponse, identification_requise=True):
    e = etat(reponse)
    if e == "soumis":
        raise Refus("Ce questionnaire a déjà été envoyé.", 409)
    if e == "ferme":
        raise Refus("La campagne n'est pas ouverte à la saisie.", 403)
    if identification_requise and not reponse.nom:
        raise Refus("Renseignez d'abord vos coordonnées.", 409)


def identifier(reponse, form):
    reponse = form.save(commit=False)
    if reponse.statut == Reponse.Statut.INVITE:
        reponse.statut = Reponse.Statut.EN_COURS
        reponse.date_debut = timezone.now()
    if not reponse.donnees.get("A01"):
        reponse.donnees["A01"] = reponse.epn.nom
        reponse.donnees["A02"] = reponse.epn.sigle
    reponse.save()
    return reponse


def _vers_querydict(valeurs):
    """Les valeurs JSON du navigateur, sous la forme attendue par les formulaires Django."""
    qd = QueryDict(mutable=True)
    for code, v in (valeurs or {}).items():
        if isinstance(v, list):
            qd.setlist(code, [str(x) for x in v])
        elif v is None or isinstance(v, bool):
            qd[code] = ""
        else:
            qd[code] = str(v)
    return qd


def _pieces(reponse):
    return {p.code: p for p in reponse.pieces.all()}


def enregistrer_module(reponse, code, valeurs, valider):
    """Enregistre une rubrique et renvoie les erreurs à afficher (vide si tout va bien).

    Les valeurs correctes sont toujours gardées (brouillon), même si la rubrique contient des erreurs :
    rien de ce que la personne a saisi n'est perdu. La rubrique n'est « complète » que si elle passe la
    validation entière (champs obligatoires et règles de cohérence).
    """
    mod = module_par_code(code)
    envoyees = {q["code"] for q in mod["questions"] if q["type"] != "fichier" and q["code"] in valeurs}
    donnees = _vers_querydict({c: valeurs[c] for c in envoyees})
    pieces = _pieces(reponse)

    brouillon = ModuleForm(mod, donnees, brouillon=True, pieces=pieces)
    brouillon.is_valid()  # cleaned_data ne contient que les champs au bon format
    reponse.donnees.update({c: v for c, v in brouillon.valeurs_json().items() if c in envoyees})

    complet_form = ModuleForm(mod, _vers_querydict(
        {q["code"]: reponse.donnees.get(q["code"]) for q in mod["questions"] if q["type"] != "fichier"}),
        pieces=pieces)
    complet = complet_form.is_valid()
    if complet and code not in reponse.modules_completes:
        reponse.modules_completes.append(code)
    elif not complet and code in reponse.modules_completes:
        reponse.modules_completes.remove(code)
    reponse.save()

    erreurs = complet_form.errors if valider else brouillon.errors
    return {c: [str(e) for e in liste] for c, liste in erreurs.items()}


def deposer_piece(reponse, code, fichier):
    q = next((q for m in MODULES for q in m["questions"] if q["code"] == code and q["type"] == "fichier"), None)
    if q is None:
        raise Refus("Cette question n'accepte pas de fichier.", 404)
    from django.core.exceptions import ValidationError

    try:
        valider_piece(fichier)
    except ValidationError as e:
        raise Refus(" ".join(e.messages))
    ancienne = reponse.pieces.filter(code=code).first()
    nouvelle = PieceJointe(reponse=reponse, code=code, nom_original=fichier.name[:255], taille=fichier.size)
    nouvelle.fichier.save(fichier.name, fichier, save=False)
    with transaction.atomic():
        if ancienne:
            ancienne.supprimer()
        nouvelle.save()
    reponse.donnees[code] = nouvelle.nom_original
    reponse.save(update_fields=["donnees", "date_modification"])
    return nouvelle


def supprimer_piece(reponse, code):
    piece = reponse.pieces.filter(code=code).first()
    if not piece:
        raise Refus("Aucun fichier pour cette question.", 404)
    piece.supprimer()
    reponse.donnees.pop(code, None)
    mod = next(m for m in MODULES if any(q["code"] == code for q in m["questions"]))
    q = next(q for q in mod["questions"] if q["code"] == code)
    if q.get("obligatoire", True) and mod["code"] in reponse.modules_completes:
        reponse.modules_completes.remove(mod["code"])
    reponse.save()


def soumettre(reponse, certification):
    manquants = [m["titre"] for m in MODULES if m["code"] not in reponse.modules_completes]
    if manquants:
        raise Refus("Rubriques à compléter avant l'envoi : " + ", ".join(manquants) + ".")
    if not certification:
        raise Refus("Cochez la case de certification pour envoyer.")
    with transaction.atomic():
        reponse = Reponse.objects.select_for_update().select_related("epn", "campagne").get(pk=reponse.pk)
        if reponse.est_soumise:
            return reponse
        reponse.statut = Reponse.Statut.SOUMIS
        reponse.date_soumission = timezone.now()
        reponse.save(update_fields=["statut", "date_soumission", "date_modification"])
    envoyer_accuse(reponse)
    return reponse


# --- Espace administrateur -------------------------------------------------------------------------

def campagne_demandee(params):
    cid = params.get("campagne")
    if cid:
        c = Campagne.objects.filter(pk=cid).first()
        if c is None:
            raise Refus("Campagne introuvable.", 404)
        return c
    return Campagne.courante() or Campagne.objects.first()


def filtrer(params, qs):
    if params.get("statut"):
        qs = qs.filter(statut=params["statut"])
    if params.get("tutelle"):
        qs = qs.filter(epn__tutelle=params["tutelle"])
    if params.get("categorie"):
        qs = qs.filter(epn__categorie=params["categorie"])
    if params.get("region"):
        qs = qs.filter(epn__region=params["region"])
    if params.get("q"):
        q = params["q"]
        qs = qs.filter(Q(epn__nom__icontains=q) | Q(epn__sigle__icontains=q) | Q(nom__icontains=q)
                       | Q(prenom__icontains=q))
    return qs


def historique():
    lignes = []
    for c in Campagne.objects.order_by("exercice").annotate(
        total=Count("reponses"), soumis=Count("reponses", filter=Q(reponses__statut=Reponse.Statut.SOUMIS))
    ).filter(total__gt=0):
        lignes.append({"libelle": str(c.exercice), "taux": round(100 * c.soumis / c.total) if c.total else 0})
    return lignes


def archive_pieces(reponse):
    tampon = BytesIO()
    with zipfile.ZipFile(tampon, "w", zipfile.ZIP_DEFLATED) as archive:
        for p in reponse.pieces.all():
            try:
                with p.fichier.open("rb") as f:
                    archive.writestr(f"{p.code}_{get_valid_filename(p.nom_original)}", f.read())
            except FileNotFoundError:
                continue
    return tampon.getvalue()
