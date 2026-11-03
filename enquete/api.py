"""API JSON consommée par l'interface React (même origine : session Django + jeton CSRF)."""
import functools
import json

from datetime import timedelta

from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.db.models import Count, Q
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from . import export_excel, securite, serializers, services, statistiques
from .emails import envoyer_acces, envoyer_invitation, envoyer_nouveau_lien, envoyer_relance
from .forms import CampagneForm, IdentificationForm, ImportEPNForm
from .models import EPN, Campagne, Envoi, PieceJointe, Reponse, lien_public, tutelles_autorisees
from .services import Refus

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _corps(request):
    try:
        corps = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        raise Refus("Requête invalide.")
    if not isinstance(corps, dict):
        raise Refus("Requête invalide.")
    return corps


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
def config(request):
    """Identité officielle affichée dans l'en-tête (réglée dans .env)."""
    return JsonResponse({"pays": settings.PAYS, "devise": settings.DEVISE, "ministere": settings.NOM_MINISTERE,
                         "institution": settings.NOM_INSTITUTION, "lien_public": lien_public()})


def _masquer(email):
    """Première lettre et domaine seulement : la longueur de l'adresse n'est pas révélée."""
    nom, _, domaine = email.partition("@")
    return f"{nom[:1]}•••@{domaine}"


@require_http_methods(["GET", "POST"])
@api
def formulaire_public(request):
    """Lien unique pour tous : l'entité choisit son établissement, son lien personnel part au point focal officiel.

    Le lien n'est jamais affiché ici : seul le détenteur de l'adresse e-mail officielle peut répondre.
    """
    campagne = Campagne.courante()
    if campagne is None or not campagne.est_ouverte:
        if request.method == "GET":
            return JsonResponse({"campagne": serializers.campagne(campagne), "ouverte": False, "etablissements": []})
        raise Refus("Le questionnaire n'est pas ouvert en ce moment.", 403)
    if request.method == "GET":
        return JsonResponse({"campagne": serializers.campagne(campagne), "ouverte": True, "etablissements": [
            {"id": e.pk, "nom": e.nom, "sigle": e.sigle, "tutelle": e.tutelle}
            for e in EPN.objects.filter(actif=True).only("nom", "sigle", "tutelle")]})
    if securite.trop_de_demandes_acces(request):
        raise Refus("Trop de demandes depuis cette connexion. Pour protéger les établissements, les envois sont "
                    "limités. Réessayez dans 10 minutes.", 429)
    id_epn = _corps(request).get("epn")
    if not str(id_epn).isdigit():
        raise Refus("Choisissez votre établissement dans la liste.")
    epn = EPN.objects.filter(actif=True, pk=int(id_epn)).first()
    if epn is None:
        raise Refus("Choisissez votre établissement dans la liste.")
    reponse, _ = Reponse.objects.select_related("epn", "campagne").get_or_create(campagne=campagne, epn=epn)
    deja = reponse.envois.filter(type=Envoi.Type.ACCES, succes=True,
                                 date__gte=timezone.now() - timedelta(minutes=5)).exists()
    if not deja and not envoyer_acces(reponse):
        raise Refus("Le lien n'a pas pu être envoyé : le service d'e-mail est momentanément indisponible. "
                    "Réessayez dans quelques minutes.", 502)
    return JsonResponse({"email_masque": _masquer(epn.email_contact), "deja_soumis": reponse.est_soumise,
                         "deja_envoye": deja, "epn": epn.nom})


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
    perimetre = tutelles_autorisees(user)
    return {"identifiant": user.get_username(), "nom": user.get_full_name() or user.get_username(),
            "superutilisateur": user.is_superuser, "perimetre": perimetre, "administrateur": perimetre is None}


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
    identifiant = str(corps.get("identifiant", ""))
    if securite.connexion_bloquee(identifiant, request):
        raise Refus("Trop de tentatives de connexion. Pour protéger le compte, réessayez dans 15 minutes.", 429)
    user = authenticate(request, username=identifiant, password=str(corps.get("mot_de_passe", "")))
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


def _dans_perimetre(request, qs, champ="epn__tutelle"):
    """Restreint un queryset aux établissements des tutelles visibles par le compte connecté."""
    tutelles = tutelles_autorisees(request.user)
    return qs.filter(**{f"{champ}__in": tutelles}) if tutelles else qs


def _exiger_administrateur(request):
    if tutelles_autorisees(request.user) is not None:
        raise Refus("Action réservée aux administrateurs d'enquête (compte sans limite de tutelle).", 403)


def _reponses_perimetre(request, campagne):
    return _dans_perimetre(request, campagne.reponses.select_related("epn", "campagne"))


def _reponses(request, campagne):
    return services.filtrer(request.GET, _reponses_perimetre(request, campagne))


def _reponse_perimetre(request, pk):
    return get_object_or_404(_dans_perimetre(request, Reponse.objects.select_related("epn", "campagne")), pk=pk)


@require_GET
@equipe
def options(request):
    """Listes utilisées par les filtres."""
    return JsonResponse({
        "campagnes": [serializers.campagne(c) for c in Campagne.objects.all()],
        "courante": serializers.campagne(Campagne.courante()),
        "tutelles": list(_dans_perimetre(request, EPN.objects, "tutelle").order_by("tutelle")
                         .values_list("tutelle", flat=True).distinct()),
        "regions": list(_dans_perimetre(request, EPN.objects, "tutelle").exclude(region="").order_by("region")
                        .values_list("region", flat=True).distinct()),
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
        "sans_lien": _dans_perimetre(request, EPN.objects.filter(actif=True), "tutelle").exclude(reponses__campagne=c).count(),
        "effectif_total": sum(r.donnees.get("D01") or 0 for r in soumises),
        "budget_total": sum(r.donnees.get("E01") or 0 for r in soumises),
        "par_tutelle": statistiques.taux_par_groupe(reponses, "tutelle"),
        "par_categorie": statistiques.taux_par_groupe(reponses, "categorie"),
        "retardataires": [serializers.reponse_resume(r) for r in retardataires[:8]],
        "dernieres": [serializers.reponse_resume(r) for r in
                      sorted(soumises, key=lambda r: r.date_soumission, reverse=True)[:6]],
        "indicateurs": statistiques.indicateurs(soumises),
        "historique": services.historique(tutelles_autorisees(request.user)),
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
    r = _reponse_perimetre(request, pk)
    return JsonResponse(serializers.reponse_detail(r))


@require_POST
@equipe
def reponse_action(request, pk, action):
    r = _reponse_perimetre(request, pk)
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
    elif action == "remplacer-lien":
        r.remplacer_lien()
        if _corps(request).get("envoyer"):
            if not envoyer_nouveau_lien(r, par=par):
                raise Refus("Le lien a été remplacé, mais l'e-mail n'a pas pu partir : copiez le nouveau lien "
                            "et transmettez-le au point focal.", 502)
            message = f"Nouveau lien créé et envoyé au point focal de {r.epn.nom}. L'ancien ne fonctionne plus."
        else:
            message = f"Nouveau lien créé pour {r.epn.nom}. L'ancien ne fonctionne plus."
    else:
        raise Refus("Action inconnue.", 404)
    r.refresh_from_db()
    return JsonResponse({"message": message, "reponse": serializers.reponse_detail(r)})


@require_POST
@equipe
def relancer_retardataires(request):
    c = _campagne(request)
    cibles = list(_reponses_perimetre(request, c).exclude(statut=Reponse.Statut.SOUMIS))
    ok = sum(envoyer_relance(r, par=request.user.get_username()) for r in cibles)
    return JsonResponse({"envoyees": ok, "total": len(cibles)})


@require_http_methods(["GET", "POST"])
@equipe
def liens(request):
    c = _campagne(request)
    crees = None
    if request.method == "POST":
        corps = _corps(request)
        crees = c.generer_liens(_dans_perimetre(request, EPN.objects.filter(actif=True), "tutelle"))
        if corps.get("envoyer"):
            ids = corps.get("epn") or []
            cibles = _reponses_perimetre(request, c).filter(date_invitation__isnull=True)
            if ids:
                cibles = cibles.filter(epn_id__in=ids)
            envoyees = sum(envoyer_invitation(r, par=request.user.get_username()) for r in cibles)
            return JsonResponse({"crees": crees, "envoyees": envoyees})
    qs = _reponses_perimetre(request, c).order_by("epn__nom")
    return JsonResponse({
        "campagne": serializers.campagne(c), "crees": crees, "lien_public": lien_public(),
        "sans_lien": _dans_perimetre(request, EPN.objects.filter(actif=True), "tutelle").exclude(reponses__campagne=c).count(),
        "liens": [serializers.reponse_resume(r) for r in qs],
    })


@require_GET
@equipe
def liens_xlsx(request):
    c = _campagne(request)
    qs = _reponses_perimetre(request, c).order_by("epn__nom")
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
                         "indicateurs": statistiques.indicateurs(rep), "historique": services.historique(tutelles_autorisees(request.user))})


@require_GET
@equipe
def piece_admin(request, pk):
    return fichier(get_object_or_404(_dans_perimetre(request, PieceJointe.objects, "reponse__epn__tutelle"), pk=pk))


@require_GET
@equipe
def pieces_zip(request, pk):
    r = _reponse_perimetre(request, pk)
    from django.utils.text import get_valid_filename

    nom = get_valid_filename(r.epn.sigle or r.epn.nom)
    return telechargement(services.archive_pieces(r), "application/zip", f"pieces_{nom}_{r.campagne.exercice}.zip")


@require_http_methods(["GET", "POST"])
@equipe
def epn_liste(request):
    if request.method == "POST":
        _exiger_administrateur(request)
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
    return JsonResponse({"epn": [serializers.epn(e) for e in _dans_perimetre(request, EPN.objects.all(), "tutelle")]})


@require_http_methods(["GET", "POST"])
@equipe
def campagnes(request):
    if request.method == "POST":
        _exiger_administrateur(request)
        form = CampagneForm(_corps(request))
        if not form.is_valid():
            return JsonResponse({"erreurs": {c: [str(e) for e in l] for c, l in form.errors.items()}}, status=422)
        return JsonResponse(serializers.campagne(form.save()), status=201)
    tutelles = tutelles_autorisees(request.user)
    dans = Q(reponses__epn__tutelle__in=tutelles) if tutelles else Q()
    lignes = Campagne.objects.annotate(
        total=Count("reponses", filter=dans), soumis=Count("reponses", filter=dans & Q(reponses__statut=Reponse.Statut.SOUMIS)))
    return JsonResponse({"campagnes": [serializers.campagne(c) | {"total": c.total, "soumis": c.soumis}
                                       for c in lignes]})


@require_http_methods(["PUT"])
@equipe
def campagne(request, pk):
    _exiger_administrateur(request)
    c = get_object_or_404(Campagne, pk=pk)
    form = CampagneForm(_corps(request), instance=c)
    if not form.is_valid():
        return JsonResponse({"erreurs": {k: [str(e) for e in l] for k, l in form.errors.items()}}, status=422)
    return JsonResponse(serializers.campagne(form.save()))
