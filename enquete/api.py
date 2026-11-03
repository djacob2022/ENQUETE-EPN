"""API JSON consommée par l'interface React (même origine : session Django + jeton CSRF)."""
import functools
import json

from django.contrib.auth import authenticate, login, logout
from django.db.models import Count, Q
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from . import export_excel, serializers, services, statistiques
from .emails import envoyer_invitation, envoyer_relance
from .forms import CampagneForm, IdentificationForm, ImportEPNForm
from .models import EPN, Campagne, PieceJointe, Reponse
from .services import Refus

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _corps(request):
    try:
        return json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        raise Refus("Requête invalide.")


def api(vue):
    """Transforme les refus métier en réponses JSON {erreur} avec le bon code HTTP."""
    @functools.wraps(vue)
    def enveloppe(request, *args, **kwargs):
        try:
            return vue(request, *args, **kwargs)
        except Refus as r:
            return JsonResponse({"erreur": r.message}, status=r.statut)
    return enveloppe


def equipe(vue):
    @functools.wraps(vue)
    def enveloppe(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({"erreur": "Connexion requise."}, status=401)
        if not (request.user.is_active and request.user.is_staff):
            return JsonResponse({"erreur": "Accès réservé à l'équipe d'enquête."}, status=403)
        return vue(request, *args, **kwargs)
    return api(enveloppe)


def fichier(piece):
    try:
        f = piece.fichier.open("rb")
    except FileNotFoundError:
        raise Http404("Fichier introuvable.")
    return FileResponse(f, as_attachment=True, filename=piece.nom_original)


def telechargement(contenu, type_mime, nom):
    resp = HttpResponse(contenu, content_type=type_mime)
    resp["Content-Disposition"] = f'attachment; filename="{nom}"'
    return resp


# --- Commun -----------------------------------------------------------------------------------------

@require_GET
@ensure_csrf_cookie
def csrf(request):
    return JsonResponse({"ok": True})


@require_GET
def questionnaire(request):
    return JsonResponse(serializers.questionnaire())


# --- Parcours du répondant (le jeton du lien personnel fait office d'autorisation) ----------------

def _reponse(jeton):
    return get_object_or_404(Reponse.objects.select_related("epn", "campagne"), jeton=jeton)


@require_GET
@api
def reponse(request, jeton):
    return JsonResponse(serializers.reponse_publique(_reponse(jeton)))


@require_POST
@api
def identification(request, jeton):
    r = _reponse(jeton)
    services.exiger_saisie_possible(r, identification_requise=False)
    form = IdentificationForm(_corps(request), instance=r)
    if not form.is_valid():
        return JsonResponse({"erreurs": {c: [str(e) for e in l] for c, l in form.errors.items()}}, status=422)
    r = services.identifier(r, form)
    return JsonResponse(serializers.reponse_publique(r))


@require_POST
@api
def module(request, jeton, code):
    r = _reponse(jeton)
    services.exiger_saisie_possible(r)
    corps = _corps(request)
    erreurs = services.enregistrer_module(r, code, corps.get("valeurs") or {}, valider=corps.get("valider", False))
    return JsonResponse({"erreurs": erreurs, "reponse": serializers.reponse_publique(r)},
                        status=422 if erreurs and corps.get("valider") else 200)


@require_http_methods(["GET", "POST", "DELETE"])
@api
def piece_publique(request, jeton, code):
    r = _reponse(jeton)
    if request.method == "GET":
        return fichier(get_object_or_404(PieceJointe, reponse=r, code=code))
    services.exiger_saisie_possible(r)
    if request.method == "DELETE":
        services.supprimer_piece(r, code)
    else:
        if "fichier" not in request.FILES:
            raise Refus("Aucun fichier reçu.")
        services.deposer_piece(r, code, request.FILES["fichier"])
    return JsonResponse(serializers.reponse_publique(r))


@require_POST
@api
def soumettre(request, jeton):
    r = _reponse(jeton)
    services.exiger_saisie_possible(r)
    r = services.soumettre(r, bool(_corps(request).get("certification")))
    return JsonResponse(serializers.reponse_publique(r))


# --- Authentification de l'équipe -------------------------------------------------------------------

def _moi(user):
    return {"identifiant": user.get_username(), "nom": user.get_full_name() or user.get_username(),
            "superutilisateur": user.is_superuser}


@require_GET
def moi(request):
    u = request.user
    if u.is_authenticated and u.is_staff:
        return JsonResponse(_moi(u))
    return JsonResponse({"erreur": "Non connecté."}, status=401)


@require_POST
@api
def connexion(request):
    corps = _corps(request)
    user = authenticate(request, username=corps.get("identifiant", ""), password=corps.get("mot_de_passe", ""))
    if user is None or not user.is_staff:
        raise Refus("Identifiant ou mot de passe incorrect.", 401)
    login(request, user)
    return JsonResponse(_moi(user))


@require_POST
def deconnexion(request):
    logout(request)
    return JsonResponse({"ok": True})


# --- Espace administrateur ------------------------------------------------------------------------

def _campagne(request, exiger=True):
    c = services.campagne_demandee(request.GET)
    if c is None and exiger:
        raise Refus("Aucune campagne : créez-en une.", 404)
    return c


def _reponses(request, campagne):
    return services.filtrer(request.GET, campagne.reponses.select_related("epn", "campagne"))


@require_GET
@equipe
def options(request):
    """Listes utilisées par les filtres."""
    return JsonResponse({
        "campagnes": [serializers.campagne(c) for c in Campagne.objects.all()],
        "courante": serializers.campagne(Campagne.courante()),
        "tutelles": list(EPN.objects.order_by("tutelle").values_list("tutelle", flat=True).distinct()),
        "regions": list(EPN.objects.exclude(region="").order_by("region").values_list("region", flat=True).distinct()),
        "categories": [{"valeur": v, "libelle": l} for v, l in EPN.Categorie.choices],
        "statuts": [{"valeur": v, "libelle": l} for v, l in Reponse.Statut.choices],
    })


@require_GET
@equipe
def tableau_de_bord(request):
    c = _campagne(request)
    reponses = list(_reponses(request, c))
    compte = {s: 0 for s, _ in Reponse.Statut.choices}
    for r in reponses:
        compte[r.statut] += 1
    soumises = [r for r in reponses if r.est_soumise]
    retardataires = sorted([r for r in reponses if not r.est_soumise], key=lambda r: (-r.avancement(), r.epn.nom))
    return JsonResponse({
        "campagne": serializers.campagne(c),
        "invites": len(reponses),
        "compte": compte,
        "taux": round(100 * len(soumises) / len(reponses)) if reponses else 0,
        "sans_lien": EPN.objects.filter(actif=True).exclude(reponses__campagne=c).count(),
        "effectif_total": sum(r.donnees.get("D01") or 0 for r in soumises),
        "budget_total": sum(r.donnees.get("E01") or 0 for r in soumises),
        "par_tutelle": statistiques.taux_par_groupe(reponses, "tutelle"),
        "par_categorie": statistiques.taux_par_groupe(reponses, "categorie"),
        "retardataires": [serializers.reponse_resume(r) for r in retardataires[:8]],
        "dernieres": [serializers.reponse_resume(r) for r in
                      sorted(soumises, key=lambda r: r.date_soumission, reverse=True)[:6]],
        "indicateurs": statistiques.indicateurs(soumises),
        "historique": services.historique(),
    })


@require_GET
@equipe
def reponses(request):
    c = _campagne(request)
    qs = _reponses(request, c).order_by("epn__nom")
    return JsonResponse({"campagne": serializers.campagne(c), "reponses": [serializers.reponse_resume(r) for r in qs]})


@require_GET
@equipe
def reponse_detail(request, pk):
    r = get_object_or_404(Reponse.objects.select_related("epn", "campagne"), pk=pk)
    return JsonResponse(serializers.reponse_detail(r))


@require_POST
@equipe
def reponse_action(request, pk, action):
    r = get_object_or_404(Reponse.objects.select_related("epn", "campagne"), pk=pk)
    par = request.user.get_username()
    if action == "rouvrir":
        if not r.est_soumise:
            raise Refus("Cette réponse n'est pas envoyée.")
        r.statut = Reponse.Statut.EN_COURS
        r.date_soumission = None
        r.save(update_fields=["statut", "date_soumission", "date_modification"])
        message = f"Réponse de {r.epn.nom} rouverte : l'EPN peut la corriger avec son lien."
    elif action == "relancer":
        if r.est_soumise:
            raise Refus("Cet EPN a déjà envoyé ses réponses.")
        if not envoyer_relance(r, par=par):
            raise Refus("La relance n'a pas pu être envoyée (serveur d'e-mails).", 502)
        message = f"Relance envoyée à {r.epn.nom}."
    elif action == "inviter":
        if not envoyer_invitation(r, par=par):
            raise Refus("L'invitation n'a pas pu être envoyée (serveur d'e-mails).", 502)
        message = f"Invitation envoyée à {r.epn.nom}."
    else:
        raise Refus("Action inconnue.", 404)
    r.refresh_from_db()
    return JsonResponse({"message": message, "reponse": serializers.reponse_detail(r)})


@require_POST
@equipe
def relancer_retardataires(request):
    c = _campagne(request)
    cibles = list(c.reponses.select_related("epn", "campagne").exclude(statut=Reponse.Statut.SOUMIS))
    ok = sum(envoyer_relance(r, par=request.user.get_username()) for r in cibles)
    return JsonResponse({"envoyees": ok, "total": len(cibles)})


@require_http_methods(["GET", "POST"])
@equipe
def liens(request):
    c = _campagne(request)
    crees = None
    if request.method == "POST":
        corps = _corps(request)
        crees = c.generer_liens()
        if corps.get("envoyer"):
            ids = corps.get("epn") or []
            cibles = c.reponses.select_related("epn", "campagne").filter(date_invitation__isnull=True)
            if ids:
                cibles = cibles.filter(epn_id__in=ids)
            envoyees = sum(envoyer_invitation(r, par=request.user.get_username()) for r in cibles)
            return JsonResponse({"crees": crees, "envoyees": envoyees})
    qs = c.reponses.select_related("epn", "campagne").order_by("epn__nom")
    return JsonResponse({
        "campagne": serializers.campagne(c), "crees": crees,
        "sans_lien": EPN.objects.filter(actif=True).exclude(reponses__campagne=c).count(),
        "liens": [serializers.reponse_resume(r) for r in qs],
    })


@require_GET
@equipe
def liens_xlsx(request):
    c = _campagne(request)
    qs = c.reponses.select_related("epn", "campagne").order_by("epn__nom")
    return telechargement(export_excel.classeur_liens(c, qs), XLSX, f"liens_EPN_{c.exercice}.xlsx")


@require_GET
@equipe
def export_xlsx(request):
    c = _campagne(request)
    qs = _reponses(request, c)
    if request.GET.get("toutes") != "1" and not request.GET.get("statut"):
        qs = qs.filter(statut=Reponse.Statut.SOUMIS)
    return telechargement(export_excel.classeur(c, list(qs.order_by("epn__nom"))), XLSX, export_excel.nom_fichier(c))


@require_GET
@equipe
def stats(request):
    c = _campagne(request)
    qs = _reponses(request, c)
    if request.GET.get("toutes") != "1":
        qs = qs.filter(statut=Reponse.Statut.SOUMIS)
    rep = list(qs)
    blocs = []
    for b in statistiques.par_question(rep):
        blocs.append({"code": b["module"]["code"], "titre": b["module"]["titre"], "questions": [
            {"code": i["q"]["code"], "libelle": i["q"]["libelle"], "type": i["q"]["type"], "genre": i["genre"],
             "stats": i["stats"]} for i in b["questions"]]})
    return JsonResponse({"campagne": serializers.campagne(c), "n": len(rep), "blocs": blocs,
                         "indicateurs": statistiques.indicateurs(rep), "historique": services.historique()})


@require_GET
@equipe
def piece_admin(request, pk):
    return fichier(get_object_or_404(PieceJointe, pk=pk))


@require_GET
@equipe
def pieces_zip(request, pk):
    r = get_object_or_404(Reponse.objects.select_related("epn", "campagne"), pk=pk)
    from django.utils.text import get_valid_filename

    nom = get_valid_filename(r.epn.sigle or r.epn.nom)
    return telechargement(services.archive_pieces(r), "application/zip", f"pieces_{nom}_{r.campagne.exercice}.zip")


@require_http_methods(["GET", "POST"])
@equipe
def epn_liste(request):
    if request.method == "POST":
        form = ImportEPNForm(request.POST, request.FILES)
        if not form.is_valid():
            raise Refus(" ".join(e for l in form.errors.values() for e in l))
        lignes, erreurs = export_excel.lire_epn(form.cleaned_data["fichier"])
        crees = maj = 0
        for ligne in lignes:
            _, cree = EPN.objects.update_or_create(nom=ligne.pop("nom"), defaults=ligne)
            crees += cree
            maj += not cree
        return JsonResponse({"crees": crees, "mis_a_jour": maj, "erreurs": erreurs[:50]})
    return JsonResponse({"epn": [serializers.epn(e) for e in EPN.objects.all()]})


@require_http_methods(["GET", "POST"])
@equipe
def campagnes(request):
    if request.method == "POST":
        form = CampagneForm(_corps(request))
        if not form.is_valid():
            return JsonResponse({"erreurs": {c: [str(e) for e in l] for c, l in form.errors.items()}}, status=422)
        return JsonResponse(serializers.campagne(form.save()), status=201)
    lignes = Campagne.objects.annotate(
        total=Count("reponses"), soumis=Count("reponses", filter=Q(reponses__statut=Reponse.Statut.SOUMIS)))
    return JsonResponse({"campagnes": [serializers.campagne(c) | {"total": c.total, "soumis": c.soumis}
                                       for c in lignes]})


@require_http_methods(["PUT"])
@equipe
def campagne(request, pk):
    c = get_object_or_404(Campagne, pk=pk)
    form = CampagneForm(_corps(request), instance=c)
    if not form.is_valid():
        return JsonResponse({"erreurs": {k: [str(e) for e in l] for k, l in form.errors.items()}}, status=422)
    return JsonResponse(serializers.campagne(form.save()))
