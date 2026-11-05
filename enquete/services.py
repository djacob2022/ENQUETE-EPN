"""Logique métier partagée par l'API : saisie du questionnaire, pièces jointes, soumission, filtres."""
import json
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
from .questionnaire import condition_remplie


class Refus(Exception):
    """Action impossible dans l'état actuel (message destiné à l'utilisateur)."""

    def __init__(self, message, statut=400):
        super().__init__(message)
        self.message = message
        self.statut = statut


def module_par_code(reponse, code):
    m = reponse.campagne.q.module(code)
    if m is None:
        raise Refus("Rubrique inconnue.", 404)
    return m


def etat(reponse):
    """« soumis » (transmise, verrouillée), « ferme » (hors délai) ou « ouvert » (saisie possible)."""
    if reponse.est_soumise:
        return "soumis"
    if not reponse.campagne.active:
        return "ferme"
    aujourd_hui = timezone.localdate()
    if aujourd_hui < reponse.campagne.date_ouverture:
        return "ferme"
    # Délai : la date de clôture, ou la prolongation accordée à cet EPN (F-20). Une réponse renvoyée pour
    # correction reste modifiable tant que la campagne est active.
    if aujourd_hui > reponse.date_limite_effective and reponse.statut != Reponse.Statut.A_CORRIGER:
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
        if isinstance(v, list) and v and isinstance(v[0], dict):
            qd[code] = json.dumps(v)  # tableau à lignes répétables
        elif isinstance(v, list):
            qd.setlist(code, [str(x) for x in v])
        elif v is None or isinstance(v, bool):
            qd[code] = ""
        else:
            qd[code] = str(v)
    return qd


def _pieces(reponse):
    return {p.code: p for p in reponse.pieces.all()}


def _formulaire_complet(reponse, mod, pieces):
    q = reponse.campagne.q
    valeurs = {x["code"]: reponse.donnees.get(x["code"]) for x in mod["questions"] if x["type"] != "fichier"}
    return ModuleForm(mod, _vers_querydict(valeurs), pieces=pieces, regles=q.regles_du_module(mod["code"]),
                      contexte=reponse.donnees)


def recalculer_completude(reponse, pieces=None):
    """Recalcule la liste des rubriques complètes (une réponse peut en changer une autre via les conditions)."""
    pieces = _pieces(reponse) if pieces is None else pieces
    completes = [m["code"] for m in reponse.campagne.q.modules if _formulaire_complet(reponse, m, pieces).is_valid()]
    reponse.modules_completes = completes
    return completes


def _effacer_masquees(reponse):
    """Une question devenue sans objet (condition non remplie) perd sa réponse : pas de donnée fantôme."""
    for _, q in reponse.campagne.q.questions():
        if q["type"] != "fichier" and not condition_remplie(q, reponse.donnees) and reponse.donnees.get(q["code"]) not in (None, "", []):
            reponse.donnees[q["code"]] = None


def enregistrer_module(reponse, code, valeurs, valider):
    """Enregistre une rubrique et renvoie les erreurs à afficher (vide si tout va bien).

    Les valeurs correctes sont toujours gardées (brouillon), même si la rubrique contient des erreurs :
    rien de ce que la personne a saisi n'est perdu. La rubrique n'est « complète » que si elle passe la
    validation entière (champs obligatoires, conditions d'affichage et règles de cohérence).
    """
    mod = module_par_code(reponse, code)
    envoyees = {q["code"] for q in mod["questions"] if q["type"] != "fichier" and q["code"] in valeurs}
    donnees = _vers_querydict({c: valeurs[c] for c in envoyees})
    pieces = _pieces(reponse)

    brouillon = ModuleForm(mod, donnees, brouillon=True, pieces=pieces, contexte=reponse.donnees | dict(valeurs))
    brouillon.is_valid()  # cleaned_data ne contient que les champs au bon format
    reponse.donnees.update({c: v for c, v in brouillon.valeurs_json().items() if c in envoyees})
    _effacer_masquees(reponse)

    complet_form = _formulaire_complet(reponse, mod, pieces)
    complet_form.is_valid()
    recalculer_completude(reponse, pieces)
    reponse.save()

    # À la validation : champs manquants et règles de cohérence, plus les erreurs de format de la saisie en cours.
    erreurs = (complet_form.errors | brouillon.errors) if valider else brouillon.errors
    return {c: [str(e) for e in liste] for c, liste in erreurs.items() if c != "__all__"}


def deposer_piece(reponse, code, fichier):
    q = reponse.campagne.q.question(code)
    if q is None or q["type"] != "fichier":
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
    recalculer_completude(reponse)
    reponse.save()
    return nouvelle


def supprimer_piece(reponse, code):
    piece = reponse.pieces.filter(code=code).first()
    if not piece:
        raise Refus("Aucun fichier pour cette question.", 404)
    piece.supprimer()
    reponse.donnees.pop(code, None)
    recalculer_completude(reponse)
    reponse.save()


def soumettre(reponse, certification):
    recalculer_completude(reponse)
    manquants = [m["titre"] for m in reponse.campagne.q.modules if m["code"] not in reponse.modules_completes]
    if manquants:
        reponse.save(update_fields=["modules_completes"])
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


def reponse_precedente(reponse):
    """La réponse du même EPN à la campagne précédente (F-24, F-32, F-40)."""
    return (Reponse.objects.filter(epn=reponse.epn, campagne__exercice__lt=reponse.campagne.exercice)
            .exclude(donnees={}).order_by("-campagne__exercice").select_related("campagne").first())


def preremplir(reponse, code_module):
    """Reprend, pour une rubrique, les réponses de la campagne précédente (questions de même code, hors fichiers)."""
    precedente = reponse_precedente(reponse)
    if precedente is None:
        raise Refus("Aucune réponse de votre établissement à une campagne précédente.", 404)
    mod = module_par_code(reponse, code_module)
    repris = 0
    for q in mod["questions"]:
        v = precedente.donnees.get(q["code"])
        if q["type"] != "fichier" and v not in (None, "", []):
            reponse.donnees[q["code"]] = v
            repris += 1
    _effacer_masquees(reponse)
    recalculer_completude(reponse)
    reponse.save()
    return repris, precedente.campagne


# --- Circuit de validation (F-29, F-30, F-20) ------------------------------------------------------

def prendre_en_revue(reponse, par):
    if reponse.statut != Reponse.Statut.SOUMIS:
        raise Refus("Seule une réponse soumise peut être prise en revue.")
    reponse.statut = Reponse.Statut.EN_REVUE
    reponse.save(update_fields=["statut", "date_modification"])


def valider(reponse, par):
    if reponse.statut not in (Reponse.Statut.SOUMIS, Reponse.Statut.EN_REVUE):
        raise Refus("Seule une réponse soumise ou en revue peut être validée.")
    reponse.statut = Reponse.Statut.VALIDE
    reponse.date_validation = timezone.now()
    reponse.valide_par = par
    reponse.commentaires = {}
    reponse.save(update_fields=["statut", "date_validation", "valide_par", "commentaires", "date_modification"])


def renvoyer_pour_correction(reponse, commentaires, par):
    """Renvoie la réponse à l'EPN avec un commentaire général et/ou par question ; il corrige puis renvoie."""
    if not reponse.est_soumise:
        raise Refus("Cette réponse n'a pas été envoyée.")
    q = reponse.campagne.q
    propres = {}
    for code, texte in (commentaires or {}).items():
        texte = str(texte or "").strip()[:2000]
        if texte and (code == "general" or q.question(code)):
            propres[code] = texte
    if not propres:
        raise Refus("Écrivez au moins un commentaire pour expliquer la correction attendue.")
    reponse.statut = Reponse.Statut.A_CORRIGER
    reponse.commentaires = propres
    reponse.date_soumission = None
    reponse.date_validation = None
    reponse.valide_par = ""
    reponse.save()
    return propres


def rouvrir(reponse):
    if not reponse.est_soumise:
        raise Refus("Cette réponse n'est pas envoyée.")
    reponse.statut = Reponse.Statut.EN_COURS
    reponse.date_soumission = None
    reponse.date_validation = None
    reponse.valide_par = ""
    reponse.save(update_fields=["statut", "date_soumission", "date_validation", "valide_par", "date_modification"])


def prolonger(reponse, texte_date):
    import datetime

    if not texte_date:
        reponse.date_limite = None
    else:
        try:
            jour = datetime.date.fromisoformat(str(texte_date))
        except ValueError:
            raise Refus("Date invalide.")
        if jour <= reponse.campagne.date_cloture:
            raise Refus("Le nouveau délai doit être postérieur à la clôture de la campagne.")
        reponse.date_limite = jour
    reponse.save(update_fields=["date_limite", "date_modification"])


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


def historique(tutelles=None):
    dans = Q(reponses__epn__tutelle__in=tutelles) if tutelles else Q()
    lignes = []
    for c in Campagne.objects.order_by("exercice").annotate(
        total=Count("reponses", filter=dans),
        soumis=Count("reponses", filter=dans & Q(reponses__statut__in=Reponse.ENVOYES)),
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
