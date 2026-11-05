"""API JSON consommée par l'interface React (même origine : session Django + jeton CSRF)."""
import functools
import json
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from . import editeur, export_excel, securite, serializers, services, statistiques
from .emails import (envoyer_acces, envoyer_correction, envoyer_invitation, envoyer_lien_mot_de_passe,
                     envoyer_nouveau_lien, envoyer_relance, envoyer_validation)
from .forms import CampagneForm, EPNForm, IdentificationForm, ImportEPNForm
from .journal import LIBELLES, tracer
from .models import (EPN, Campagne, Envoi, Journal, ListeReference, Parametres, PieceJointe, ProfilEquipe, Reponse,
                     lien_public, permissions_de, role_de, tutelles_autorisees)
from .services import Refus

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
User = get_user_model()


def _corps(request):
    try:
        corps = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        raise Refus("Requête invalide.")
    if not isinstance(corps, dict):
        raise Refus("Requête invalide.")
    return corps


def _erreurs(form):
    return JsonResponse({"erreurs": {c: [str(e) for e in l] for c, l in form.errors.items()}}, status=422)


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


MESSAGES_DROITS = {
    "voir_nominatif": "Votre rôle donne accès aux tableaux de bord agrégés seulement.",
    "exporter": "Votre rôle ne permet pas d'exporter les données.",
    "valider": "Action réservée aux superviseurs de tutelle et aux administrateurs.",
    "relancer": "Action réservée aux superviseurs de tutelle et aux administrateurs.",
    "gerer_liens": "Action réservée aux superviseurs de tutelle et aux administrateurs.",
    "voir_journal": "Journal réservé aux administrateurs.",
    "gerer_comptes": "Gestion des comptes réservée aux administrateurs.",
}


def _exiger(request, permission):
    """Contrôle des droits côté serveur, sur chaque requête (section 7)."""
    if permission not in permissions_de(request.user):
        raise Refus(MESSAGES_DROITS.get(permission, "Action réservée aux administrateurs d'enquête (compte sans "
                                                     "limite de tutelle)."), 403)


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


def _detail_reponse(r):
    return {"reponse": r.pk, "epn": r.epn.nom, "tutelle": r.epn.tutelle, "campagne": r.campagne_id}


# --- Commun -----------------------------------------------------------------------------------------

@require_GET
@ensure_csrf_cookie
def csrf(request):
    return JsonResponse({"ok": True})


@require_GET
def sante(request):
    """Contrôle de santé (Docker, supervision) : l'application répond et la base de données est joignable."""
    from django.db import connection

    try:
        with connection.cursor() as curseur:
            curseur.execute("SELECT 1")
    except Exception:
        return JsonResponse({"etat": "base de données injoignable"}, status=503)
    return JsonResponse({"etat": "ok"})


@require_GET
def config(request):
    """Identité officielle affichée dans l'en-tête (réglée dans Paramètres, à défaut dans .env)."""
    p = Parametres.charger()
    return JsonResponse({"pays": p.valeur("pays"), "devise": p.valeur("devise"), "ministere": p.valeur("ministere"),
                         "institution": p.valeur("institution"), "monnaie": p.monnaie, "assistance": p.email_contact,
                         "logo": "/api/logo/" if p.logo else None, "lien_public": lien_public()})


@require_GET
def logo(request):
    p = Parametres.charger()
    if not p.logo:
        raise Http404()
    try:
        return FileResponse(p.logo.open("rb"), content_type="image/png" if p.logo.name.endswith(".png") else "image/jpeg")
    except FileNotFoundError:
        raise Http404()


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
    cibles = campagne.epn_cibles()
    if request.method == "GET":
        return JsonResponse({"campagne": serializers.campagne(campagne), "ouverte": True, "etablissements": [
            {"id": e.pk, "nom": e.nom, "sigle": e.sigle, "tutelle": e.tutelle}
            for e in cibles.only("nom", "sigle", "tutelle")]})
    if securite.trop_de_demandes_acces(request):
        raise Refus("Trop de demandes depuis cette connexion. Pour protéger les établissements, les envois sont "
                    "limités. Réessayez dans 10 minutes.", 429)
    id_epn = _corps(request).get("epn")
    if not str(id_epn).isdigit():
        raise Refus("Choisissez votre établissement dans la liste.")
    epn = cibles.filter(pk=int(id_epn)).first()
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
@api
def questionnaire(request):
    """Questionnaire d'une campagne (?campagne=id), par défaut celui de la campagne en cours."""
    c = services.campagne_demandee(request.GET)
    if c is None:
        raise Refus("Aucune campagne.", 404)
    return JsonResponse(serializers.questionnaire(c))


# --- Parcours du répondant (le jeton du lien personnel fait office d'autorisation) ----------------

def _reponse(jeton):
    return get_object_or_404(Reponse.objects.select_related("epn", "campagne"), jeton=jeton)


def _repondant(r):
    return f"EPN : {r.epn.sigle or r.epn.nom}"[:150]


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
        return _erreurs(form)
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


@require_POST
@api
def preremplir(request, jeton, code):
    """F-24 : reprend dans la rubrique les réponses de la campagne précédente."""
    r = _reponse(jeton)
    services.exiger_saisie_possible(r)
    repris, precedente = services.preremplir(r, code)
    tracer(request, "preremplissage", r.epn.nom, auteur=_repondant(r), module=code, repris=repris,
           **_detail_reponse(r))
    return JsonResponse({"repris": repris, "exercice": precedente.exercice, "reponse": serializers.reponse_publique(r)})


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
    tracer(request, "soumission", r.epn.nom, auteur=_repondant(r), certifie_par=r.repondant, **_detail_reponse(r))
    return JsonResponse(serializers.reponse_publique(r))


# --- Authentification de l'équipe -------------------------------------------------------------------

def _moi(user):
    perimetre = tutelles_autorisees(user)
    role = role_de(user)
    perms = permissions_de(user)
    libelles = dict(ProfilEquipe.Role.choices) | {"super_administrateur": "Super-administrateur"}
    return {"identifiant": user.get_username(), "nom": user.get_full_name() or user.get_username(),
            "email": user.email, "superutilisateur": user.is_superuser, "perimetre": perimetre,
            "administrateur": "gerer_campagnes" in perms, "role": role, "role_libelle": libelles.get(role, role),
            "permissions": sorted(perms), "session_minutes": settings.SESSION_COOKIE_AGE // 60}


@require_GET
def moi(request):
    u = request.user
    if u.is_authenticated and u.is_staff:
        return JsonResponse(_moi(u))
    return JsonResponse({"erreur": "Non connecté."}, status=401)


def _identifiant(texte):
    """Connexion par e-mail (F-01) ou par identifiant."""
    texte = texte.strip()
    if "@" in texte:
        u = User.objects.filter(email__iexact=texte, is_active=True).order_by("pk").first()
        if u:
            return u.get_username()
    return texte


@require_POST
@api
def connexion(request):
    corps = _corps(request)
    identifiant = _identifiant(str(corps.get("identifiant", "")))
    if securite.connexion_bloquee(identifiant, request):
        raise Refus("Trop de tentatives de connexion. Pour protéger le compte, réessayez dans 15 minutes.", 429)
    user = authenticate(request, username=identifiant, password=str(corps.get("mot_de_passe", "")))
    if user is None or not user.is_staff:
        tracer(request, "connexion_echec", identifiant, auteur=identifiant)
        raise Refus("Identifiant ou mot de passe incorrect.", 401)
    login(request, user)
    tracer(request, "connexion", user.get_username())
    return JsonResponse(_moi(user))


@require_POST
def deconnexion(request):
    if request.user.is_authenticated:
        tracer(request, "deconnexion", request.user.get_username())
    logout(request)
    return JsonResponse({"ok": True})


def lien_mot_de_passe(user):
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    return f"{settings.SITE_URL}/mot-de-passe/{uid}/{default_token_generator.make_token(user)}"


@require_POST
@api
def mot_de_passe_oublie(request):
    """F-02 : envoie un lien de réinitialisation. La réponse est identique que l'adresse existe ou non."""
    if securite.trop_de_demandes_acces(request):
        raise Refus("Trop de demandes depuis cette connexion. Réessayez dans 10 minutes.", 429)
    email = str(_corps(request).get("email", "")).strip()
    if "@" not in email:
        raise Refus("Indiquez l'adresse e-mail de votre compte.")
    for user in User.objects.filter(email__iexact=email, is_active=True, is_staff=True):
        envoyer_lien_mot_de_passe(user, lien_mot_de_passe(user))
        tracer(request, "mot_de_passe_demande", user.get_username(), auteur=user.get_username())
    return JsonResponse({"ok": True})


@require_POST
@api
def nouveau_mot_de_passe(request):
    corps = _corps(request)
    try:
        user = User.objects.get(pk=force_str(urlsafe_base64_decode(str(corps.get("uid", "")))), is_active=True)
    except (User.DoesNotExist, ValueError, TypeError, OverflowError):
        user = None
    if user is None or not default_token_generator.check_token(user, str(corps.get("jeton", ""))):
        raise Refus("Ce lien n'est plus valable (déjà utilisé ou expiré). Demandez-en un nouveau.", 400)
    mot_de_passe = str(corps.get("mot_de_passe", ""))
    try:
        validate_password(mot_de_passe, user)
    except ValidationError as e:
        return JsonResponse({"erreurs": {"mot_de_passe": e.messages}}, status=422)
    user.set_password(mot_de_passe)
    user.save(update_fields=["password"])
    tracer(request, "mot_de_passe_change", user.get_username(), auteur=user.get_username())
    return JsonResponse({"ok": True, "identifiant": user.get_username()})


# --- Espace de gestion ------------------------------------------------------------------------------

def _campagne(request, exiger=True):
    c = services.campagne_demandee(request.GET)
    if c is None and exiger:
        raise Refus("Aucune campagne : créez-en une.", 404)
    return c


def _dans_perimetre(request, qs, champ="epn__tutelle"):
    """Restreint un queryset aux établissements des tutelles visibles par le compte connecté."""
    tutelles = tutelles_autorisees(request.user)
    return qs.filter(**{f"{champ}__in": tutelles}) if tutelles else qs


def _reponses_perimetre(request, campagne):
    return _dans_perimetre(request, campagne.reponses.select_related("epn", "campagne"))


def _reponses(request, campagne):
    return services.filtrer(request.GET, _reponses_perimetre(request, campagne))


def _reponse_perimetre(request, pk):
    return get_object_or_404(_dans_perimetre(request, Reponse.objects.select_related("epn", "campagne")), pk=pk)


BASES = {"validees": ("valide",), "envoyees": Reponse.ENVOYES}


def _base(request, qs):
    """Les statistiques et exports portent par défaut sur les réponses validées (section 6.3)."""
    base = request.GET.get("base", "validees")
    if request.GET.get("statut"):
        return qs, "statut"
    if base in BASES:
        return qs.filter(statut__in=BASES[base]), base
    return qs, "toutes"


@require_GET
@equipe
def options(request):
    """Listes utilisées par les filtres."""
    def refs(type_):
        return list(ListeReference.objects.filter(type=type_).values_list("libelle", flat=True))
    epns = _dans_perimetre(request, EPN.objects, "tutelle")
    return JsonResponse({
        "campagnes": [serializers.campagne(c) for c in Campagne.objects.all()],
        "courante": serializers.campagne(Campagne.courante()),
        "tutelles": sorted(set(epns.values_list("tutelle", flat=True)) | (set() if tutelles_autorisees(request.user)
                                                                          else set(refs("tutelle")))),
        "regions": sorted(set(epns.exclude(region="").values_list("region", flat=True)) | set(refs("region"))),
        "secteurs": sorted(set(epns.exclude(secteur="").values_list("secteur", flat=True)) | set(refs("secteur"))),
        "categories": [{"valeur": v, "libelle": l} for v, l in EPN.Categorie.choices],
        "etats": [{"valeur": v, "libelle": l} for v, l in EPN.Etat.choices],
        "statuts": [{"valeur": v, "libelle": l} for v, l in Reponse.Statut.choices],
        "roles": [{"valeur": v, "libelle": l} for v, l in ProfilEquipe.Role.choices],
    })


@require_GET
@equipe
def tableau_de_bord(request):
    c = _campagne(request)
    reponses = list(_reponses(request, c))
    compte = {s: 0 for s, _ in Reponse.Statut.choices}
    for r in reponses:
        compte[r.statut] += 1
    envoyees = [r for r in reponses if r.est_soumise]
    validees = [r for r in reponses if r.est_validee]
    nominatif = "voir_nominatif" in permissions_de(request.user)
    resume = serializers.reponse_resume if nominatif else (lambda r: serializers.anonymiser(serializers.reponse_resume(r)))
    retardataires = sorted([r for r in reponses if not r.est_soumise], key=lambda r: (-r.avancement(), r.epn.nom))
    a_examiner = sorted([r for r in reponses if r.statut in ("soumis", "en_revue")], key=lambda r: r.date_soumission)
    base = validees if validees else envoyees
    return JsonResponse({
        "campagne": serializers.campagne(c),
        "invites": len(reponses),
        "compte": compte,
        "taux": round(100 * len(envoyees) / len(reponses)) if reponses else 0,
        "taux_validation": round(100 * len(validees) / len(reponses)) if reponses else 0,
        "sans_lien": c.epn_cibles(_dans_perimetre(request, EPN.objects.filter(actif=True), "tutelle"))
        .exclude(reponses__campagne=c).count(),
        "base_indicateurs": "validees" if validees else "envoyees",
        "n_indicateurs": len(base),
        "nombre_epn": _dans_perimetre(request, EPN.objects.filter(actif=True), "tutelle").count(),
        "effectif_total": sum(r.donnees.get("D01") or 0 for r in base),
        "budget_total": sum(r.donnees.get("E01") or 0 for r in base),
        "par_tutelle": statistiques.taux_par_groupe(reponses, "tutelle"),
        "par_categorie": statistiques.taux_par_groupe(reponses, "categorie"),
        "par_region": statistiques.taux_par_groupe(reponses, "region"),
        "retardataires": [resume(r) for r in retardataires[:8]],
        "a_examiner": [resume(r) for r in a_examiner[:8]],
        "dernieres": [resume(r) for r in sorted(envoyees, key=lambda r: r.date_soumission or timezone.now(),
                                                reverse=True)[:6]],
        "indicateurs": statistiques.indicateurs(base),
        "historique": services.historique(tutelles_autorisees(request.user)),
    })


@require_GET
@equipe
def reponses(request):
    _exiger(request, "voir_nominatif")
    c = _campagne(request)
    qs = _reponses(request, c).order_by("epn__nom")
    return JsonResponse({"campagne": serializers.campagne(c), "reponses": [serializers.reponse_resume(r) for r in qs]})


@require_GET
@equipe
def reponse_detail(request, pk):
    _exiger(request, "voir_nominatif")
    r = _reponse_perimetre(request, pk)
    return JsonResponse(serializers.reponse_detail(r))


@require_GET
@equipe
def reponse_export(request, pk):
    """F-33 : la réponse d'un EPN, une feuille par module."""
    _exiger(request, "exporter")
    r = _reponse_perimetre(request, pk)
    from django.utils.text import get_valid_filename

    tracer(request, "export", f"Réponse de {r.epn.nom}", format="xlsx", **_detail_reponse(r))
    nom = get_valid_filename(r.epn.sigle or r.epn.nom)
    return telechargement(export_excel.classeur_reponse(r), XLSX, f"EPN_{nom}_{r.campagne.exercice}.xlsx")


ACTIONS = {
    "revue": "valider", "valider": "valider", "corriger": "valider", "rouvrir": "valider", "prolonger": "valider",
    "relancer": "relancer", "inviter": "gerer_liens", "remplacer-lien": "gerer_liens",
}


@require_POST
@equipe
def reponse_action(request, pk, action):
    if action not in ACTIONS:
        raise Refus("Action inconnue.", 404)
    _exiger(request, ACTIONS[action])
    r = _reponse_perimetre(request, pk)
    par = request.user.get_username()
    corps = _corps(request)
    detail = _detail_reponse(r)
    if action == "revue":
        services.prendre_en_revue(r, par)
        tracer(request, "revue", r.epn.nom, **detail)
        message = f"Réponse de {r.epn.nom} prise en revue."
    elif action == "valider":
        services.valider(r, par)
        tracer(request, "validation", r.epn.nom, **detail)
        envoyer_validation(r, par=par)
        message = f"Réponse de {r.epn.nom} validée : elle entre dans les statistiques."
    elif action == "corriger":
        commentaires = services.renvoyer_pour_correction(r, corps.get("commentaires") or {}, par)
        tracer(request, "correction", r.epn.nom, commentaires=commentaires, **detail)
        ok = envoyer_correction(r, par=par)
        message = (f"Réponse renvoyée à {r.epn.nom} pour correction." if ok else
                   f"Réponse renvoyée à {r.epn.nom} pour correction, mais l'e-mail n'a pas pu partir : prévenez le "
                   f"point focal.")
    elif action == "rouvrir":
        services.rouvrir(r)
        tracer(request, "rouverture", r.epn.nom, **detail)
        message = f"Réponse de {r.epn.nom} rouverte : l'EPN peut la corriger avec son lien."
    elif action == "prolonger":
        services.prolonger(r, corps.get("date"))
        tracer(request, "prolongation", r.epn.nom, date=str(r.date_limite or ""), **detail)
        message = (f"Délai de {r.epn.nom} prolongé jusqu'au {r.date_limite:%d/%m/%Y}." if r.date_limite
                   else f"Délai de {r.epn.nom} ramené à la date de clôture.")
    elif action == "relancer":
        if r.est_soumise:
            raise Refus("Cet EPN a déjà envoyé ses réponses.")
        if not envoyer_relance(r, par=par):
            raise Refus("La relance n'a pas pu être envoyée (serveur d'e-mails).", 502)
        tracer(request, "relance", r.epn.nom, **detail)
        message = f"Relance envoyée à {r.epn.nom}."
    elif action == "inviter":
        if not envoyer_invitation(r, par=par):
            raise Refus("L'invitation n'a pas pu être envoyée (serveur d'e-mails).", 502)
        tracer(request, "invitation", r.epn.nom, **detail)
        message = f"Invitation envoyée à {r.epn.nom}."
    else:  # remplacer-lien
        r.remplacer_lien()
        tracer(request, "nouveau_lien", r.epn.nom, envoye=bool(corps.get("envoyer")), **detail)
        if corps.get("envoyer"):
            if not envoyer_nouveau_lien(r, par=par):
                raise Refus("Le lien a été remplacé, mais l'e-mail n'a pas pu partir : copiez le nouveau lien "
                            "et transmettez-le au point focal.", 502)
            message = f"Nouveau lien créé et envoyé au point focal de {r.epn.nom}. L'ancien ne fonctionne plus."
        else:
            message = f"Nouveau lien créé pour {r.epn.nom}. L'ancien ne fonctionne plus."
    r.refresh_from_db()
    return JsonResponse({"message": message, "reponse": serializers.reponse_detail(r)})


@require_POST
@equipe
def relancer_retardataires(request):
    _exiger(request, "relancer")
    c = _campagne(request)
    cibles = list(_reponses_perimetre(request, c).exclude(statut__in=Reponse.ENVOYES))
    ok = sum(envoyer_relance(r, par=request.user.get_username()) for r in cibles)
    tracer(request, "relance", f"{ok} établissement(s)", campagne=c.pk, envoyees=ok, total=len(cibles))
    return JsonResponse({"envoyees": ok, "total": len(cibles)})


@require_http_methods(["GET", "POST"])
@equipe
def liens(request):
    _exiger(request, "gerer_liens")
    c = _campagne(request)
    crees = None
    epns = _dans_perimetre(request, EPN.objects.filter(actif=True), "tutelle")
    if request.method == "POST":
        corps = _corps(request)
        crees = c.generer_liens(epns)
        if corps.get("envoyer"):
            ids = corps.get("epn") or []
            cibles = _reponses_perimetre(request, c).filter(date_invitation__isnull=True)
            if ids:
                cibles = cibles.filter(epn_id__in=ids)
            envoyees = sum(envoyer_invitation(r, par=request.user.get_username()) for r in cibles)
            tracer(request, "invitation", f"{envoyees} établissement(s)", campagne=c.pk, envoyees=envoyees)
            return JsonResponse({"crees": crees, "envoyees": envoyees})
    qs = _reponses_perimetre(request, c).order_by("epn__nom")
    return JsonResponse({
        "campagne": serializers.campagne(c), "crees": crees, "lien_public": lien_public(),
        "sans_lien": c.epn_cibles(epns).exclude(reponses__campagne=c).count(),
        "liens": [serializers.reponse_resume(r) for r in qs],
    })


@require_GET
@equipe
def liens_xlsx(request):
    _exiger(request, "gerer_liens")
    c = _campagne(request)
    qs = _reponses_perimetre(request, c).order_by("epn__nom")
    tracer(request, "export", "Liste des liens personnels", format="xlsx", campagne=c.pk)
    return telechargement(export_excel.classeur_liens(c, qs), XLSX, f"liens_EPN_{c.exercice}.xlsx")


@require_GET
@equipe
def export_xlsx(request):
    _exiger(request, "exporter")
    c = _campagne(request)
    qs, base = _base(request, _reponses(request, c))
    tracer(request, "export", f"Export consolidé {c}", format="xlsx", base=base, n=qs.count(), campagne=c.pk,
           filtres={k: v for k, v in request.GET.items() if k != "campagne"})
    return telechargement(export_excel.classeur(c, list(qs.order_by("epn__nom"))), XLSX, export_excel.nom_fichier(c))


@require_GET
@equipe
def export_csv(request):
    _exiger(request, "exporter")
    c = _campagne(request)
    qs, base = _base(request, _reponses(request, c))
    tracer(request, "export", f"Export consolidé {c}", format="csv", base=base, n=qs.count(), campagne=c.pk)
    return telechargement(export_excel.csv_reponses(c, list(qs.order_by("epn__nom"))), "text/csv; charset=utf-8",
                          export_excel.nom_fichier(c).replace(".xlsx", ".csv"))


def _campagne_precedente(c):
    return Campagne.objects.filter(exercice__lt=c.exercice).order_by("-exercice").first()


@require_GET
@equipe
def stats(request):
    c = _campagne(request)
    qs, base = _base(request, _reponses(request, c))
    rep = list(qs)
    precedente = _campagne_precedente(c)
    rep_prec = None
    if precedente:
        rep_prec = list(_base(request, services.filtrer(request.GET, _reponses_perimetre(request, precedente)))[0])
    blocs = []
    for b in statistiques.par_question(c.q, rep, rep_prec):
        blocs.append({"code": b["module"]["code"], "titre": b["module"]["titre"], "questions": [
            {"code": i["q"]["code"], "libelle": i["q"]["libelle"], "type": i["q"]["type"], "genre": i["genre"],
             "unite": i["q"].get("unite"), "stats": i["stats"], "precedent": i.get("precedent")}
            for i in b["questions"]]})
    return JsonResponse({
        "campagne": serializers.campagne(c), "n": len(rep), "base": base, "blocs": blocs,
        "indicateurs": statistiques.indicateurs(rep),
        "precedente": {"campagne": serializers.campagne(precedente), "n": len(rep_prec),
                       "indicateurs": statistiques.indicateurs(rep_prec)} if precedente else None,
        "historique": services.historique(tutelles_autorisees(request.user)),
        "variables": statistiques.variables_croisables(c.q),
    })


@require_GET
@equipe
def croisement(request):
    """F-45 : tableau croisé de deux variables qualitatives (ou caractéristiques de l'EPN)."""
    c = _campagne(request)
    qs, _ = _base(request, _reponses(request, c))
    resultat = statistiques.tableau_croise(c.q, list(qs), request.GET.get("ligne", ""), request.GET.get("colonne", ""))
    if resultat is None:
        raise Refus("Choisissez deux variables qualitatives.")
    return JsonResponse(resultat)


@require_GET
@equipe
def stats_xlsx(request):
    """F-36 : tableaux statistiques avec graphiques Excel natifs (même classeur que l'export, sans données nominatives
    pour un lecteur : les feuilles statistiques seulement)."""
    c = _campagne(request)
    qs, base = _base(request, _reponses(request, c))
    nominatif = "exporter" in permissions_de(request.user)
    tracer(request, "export", f"Statistiques {c}", format="xlsx", base=base, n=qs.count(), campagne=c.pk)
    contenu = export_excel.classeur(c, list(qs.order_by("epn__nom")), statistiques_seules=not nominatif)
    return telechargement(contenu, XLSX, export_excel.nom_fichier(c).replace("EPN_", "Statistiques_EPN_"))


@require_GET
@equipe
def piece_admin(request, pk):
    _exiger(request, "voir_nominatif")
    return fichier(get_object_or_404(_dans_perimetre(request, PieceJointe.objects, "reponse__epn__tutelle"), pk=pk))


@require_GET
@equipe
def pieces_zip(request, pk):
    _exiger(request, "voir_nominatif")
    r = _reponse_perimetre(request, pk)
    from django.utils.text import get_valid_filename

    nom = get_valid_filename(r.epn.sigle or r.epn.nom)
    return telechargement(services.archive_pieces(r), "application/zip", f"pieces_{nom}_{r.campagne.exercice}.zip")


@require_GET
@equipe
def notifications(request):
    """F-47 : activité récente dans le périmètre du compte (réponses envoyées, corrections, validations)."""
    qs = Journal.objects.filter(action__in=["soumission", "validation", "correction", "preremplissage"])
    tutelles = tutelles_autorisees(request.user)
    if tutelles:
        qs = qs.filter(detail__tutelle__in=tutelles)
    return JsonResponse({"notifications": [
        {"id": j.pk, "date": j.date.isoformat(), "action": j.action, "libelle": LIBELLES.get(j.action, j.action),
         "objet": j.objet, "auteur": j.auteur, "reponse": j.detail.get("reponse")}
        for j in qs[:20]]})


# --- Répertoire des EPN et listes de référence (F-07, F-08) -----------------------------------------

@require_http_methods(["GET", "POST"])
@equipe
def epn_liste(request):
    if request.method == "POST":
        _exiger(request, "gerer_repertoire")
        if request.FILES:
            form = ImportEPNForm(request.POST, request.FILES)
            if not form.is_valid():
                raise Refus(" ".join(e for l in form.errors.values() for e in l))
            lignes, erreurs = export_excel.lire_epn(form.cleaned_data["fichier"])
            crees = maj = 0
            for ligne in lignes:
                nom = ligne.pop("nom")
                epn = EPN.objects.filter(nom=nom).first() or EPN(nom=nom)
                cree = epn.pk is None
                for k, v in ligne.items():
                    setattr(epn, k, v)
                epn.save()
                crees += cree
                maj += not cree
            tracer(request, "import_epn", form.cleaned_data["fichier"].name, crees=crees, mis_a_jour=maj,
                   erreurs=len(erreurs))
            return JsonResponse({"crees": crees, "mis_a_jour": maj, "erreurs": erreurs[:50]})
        form = EPNForm(_corps(request))
        if not form.is_valid():
            return _erreurs(form)
        e = form.save()
        tracer(request, "epn", e.nom, creation=True, valeurs=serializers.epn(e))
        return JsonResponse(serializers.epn(e), status=201)
    _exiger(request, "voir_nominatif")  # e-mails des points focaux
    return JsonResponse({"epn": [serializers.epn(e) for e in _dans_perimetre(request, EPN.objects.all(), "tutelle")]})


@require_http_methods(["GET", "PUT"])
@equipe
def epn_fiche(request, pk):
    _exiger(request, "voir_nominatif")
    e = get_object_or_404(_dans_perimetre(request, EPN.objects.all(), "tutelle"), pk=pk)
    if request.method == "PUT":
        _exiger(request, "gerer_repertoire")
        avant = serializers.epn(e)
        form = EPNForm(_corps(request), instance=e)
        if not form.is_valid():
            return _erreurs(form)
        e = form.save()
        apres = serializers.epn(e)
        changements = {k: [avant[k], apres[k]] for k in apres if avant.get(k) != apres[k] and k != "etat_libelle"}
        if changements:
            tracer(request, "epn", e.nom, changements=changements, epn_id=e.pk)
    historique = Journal.objects.filter(action__in=["epn", "import_epn"]).filter(
        Q(detail__epn_id=e.pk) | Q(objet=e.nom))[:30]
    return JsonResponse(serializers.epn(e) | {"historique": [
        {"date": j.date.isoformat(), "auteur": j.auteur, "changements": j.detail.get("changements"),
         "creation": j.detail.get("creation", False)} for j in historique]})


@require_http_methods(["GET", "POST"])
@equipe
def references(request):
    if request.method == "POST":
        _exiger(request, "gerer_repertoire")
        corps = _corps(request)
        type_, libelle = str(corps.get("type", "")), str(corps.get("libelle", "")).strip()[:255]
        if type_ not in ListeReference.Type.values or not libelle:
            raise Refus("Choisissez une liste et saisissez un libellé.")
        ref, cree = ListeReference.objects.get_or_create(type=type_, libelle=libelle)
        if cree:
            tracer(request, "reference", libelle, liste=type_, ajout=True)
        return JsonResponse({"id": ref.pk, "type": ref.type, "libelle": ref.libelle}, status=201 if cree else 200)
    return JsonResponse({"listes": [{"valeur": v, "libelle": l} for v, l in ListeReference.Type.choices],
                         "references": [{"id": r.pk, "type": r.type, "libelle": r.libelle,
                                         "utilisations": EPN.objects.filter(**{r.type: r.libelle}).count()}
                                        for r in ListeReference.objects.all()]})


@require_http_methods(["DELETE"])
@equipe
def reference(request, pk):
    _exiger(request, "gerer_repertoire")
    ref = get_object_or_404(ListeReference, pk=pk)
    tracer(request, "reference", ref.libelle, liste=ref.type, suppression=True)
    ref.delete()
    return JsonResponse({"ok": True})


# --- Campagnes et questionnaire (F-10 à F-19) --------------------------------------------------------

def _stats_campagnes(request):
    tutelles = tutelles_autorisees(request.user)
    dans = Q(reponses__epn__tutelle__in=tutelles) if tutelles else Q()
    return Campagne.objects.annotate(
        total=Count("reponses", filter=dans), soumis=Count("reponses", filter=dans & Q(reponses__statut__in=Reponse.ENVOYES)),
        validees=Count("reponses", filter=dans & Q(reponses__statut="valide")))


@require_http_methods(["GET", "POST"])
@equipe
def campagnes(request):
    if request.method == "POST":
        _exiger(request, "gerer_campagnes")
        corps = _corps(request)
        form = CampagneForm(corps)
        if not form.is_valid():
            return _erreurs(form)
        c = form.save(commit=False)
        # F-14 : une nouvelle campagne reprend le questionnaire de la campagne choisie (par défaut la plus récente).
        source = Campagne.objects.filter(pk=corps.get("copier_de")).first() if corps.get("copier_de") else \
            Campagne.objects.order_by("-exercice", "-pk").first()
        if source:
            c.questionnaire = dict(source.questionnaire, version=1, copie_de=source.nom)
        c.save()
        tracer(request, "campagne", c.nom, creation=True, copie_de=source.nom if source else None)
        return JsonResponse(serializers.campagne(c), status=201)
    return JsonResponse({"campagnes": [serializers.campagne(c) | {"total": c.total, "soumis": c.soumis,
                                                                  "validees": c.validees}
                                       for c in _stats_campagnes(request)]})


@require_http_methods(["PUT"])
@equipe
def campagne(request, pk):
    _exiger(request, "gerer_campagnes")
    c = get_object_or_404(Campagne, pk=pk)
    form = CampagneForm(_corps(request), instance=c)
    if not form.is_valid():
        return _erreurs(form)
    c = form.save()
    tracer(request, "campagne", c.nom, champs=sorted(form.changed_data))
    return JsonResponse(serializers.campagne(c))


@require_http_methods(["GET", "PUT"])
@equipe
def campagne_questionnaire(request, pk):
    """Éditeur de questionnaire sans code (F-10) : lecture et enregistrement de la définition complète."""
    c = get_object_or_404(Campagne, pk=pk)
    if request.method == "PUT":
        _exiger(request, "gerer_questionnaire")
        definition = editeur.enregistrer(c, _corps(request), request.user.get_username())
        tracer(request, "questionnaire", c.nom, version=definition["version"], campagne=c.pk)
        c.refresh_from_db()
    donnees = serializers.questionnaire(c, tous=True)
    donnees["avec_reponses"] = c.reponses.exclude(donnees={}).count()
    donnees["campagne"] = serializers.campagne(c)
    return JsonResponse(donnees)


# --- Comptes, journal, paramètres (F-04, F-46, F-48) -------------------------------------------------

def _compte(u):
    profil = getattr(u, "profil_equipe", None)
    return {"id": u.pk, "identifiant": u.get_username(), "email": u.email, "prenom": u.first_name, "nom": u.last_name,
            "actif": u.is_active, "superutilisateur": u.is_superuser, "role": role_de(u),
            "tutelles": profil.liste_tutelles if profil else [],
            "derniere_connexion": u.last_login.isoformat() if u.last_login else None,
            "mot_de_passe_defini": u.has_usable_password()}


def _appliquer_compte(u, corps, createur):
    role = corps.get("role", ProfilEquipe.Role.ADMINISTRATEUR)
    if role not in ProfilEquipe.Role.values:
        raise Refus("Rôle inconnu.")
    tutelles = [str(t).strip() for t in corps.get("tutelles") or [] if str(t).strip()]
    if role == ProfilEquipe.Role.SUPERVISEUR and not tutelles:
        raise Refus("Un superviseur de tutelle doit être rattaché à au moins une tutelle.")
    if u.is_superuser and not createur.is_superuser:
        raise Refus("Seul un super-administrateur peut modifier ce compte.", 403)
    u.first_name = str(corps.get("prenom", u.first_name))[:150]
    u.last_name = str(corps.get("nom", u.last_name))[:150]
    if "actif" in corps:
        if u.pk == createur.pk and not corps["actif"]:
            raise Refus("Vous ne pouvez pas désactiver votre propre compte.")
        u.is_active = bool(corps["actif"])
    u.is_staff = True
    u.save()
    ProfilEquipe.objects.update_or_create(utilisateur=u, defaults={"role": role, "tutelles": ", ".join(tutelles)})


@require_http_methods(["GET", "POST"])
@equipe
def comptes(request):
    _exiger(request, "gerer_comptes")
    if request.method == "POST":
        corps = _corps(request)
        email = str(corps.get("email", "")).strip().lower()
        if "@" not in email:
            raise Refus("Adresse e-mail invalide.")
        if User.objects.filter(Q(email__iexact=email) | Q(username__iexact=email)).exists():
            raise Refus("Un compte existe déjà avec cette adresse.")
        from django.db import transaction

        with transaction.atomic():  # un rôle invalide n'en laisse pas un compte à moitié créé
            u = User(username=email, email=email, is_staff=True)
            u.set_unusable_password()  # la personne choisit son mot de passe via le lien reçu
            u.save()
            _appliquer_compte(u, corps, request.user)
        ok = envoyer_lien_mot_de_passe(u, lien_mot_de_passe(u), nouveau_compte=True)
        tracer(request, "compte", email, creation=True, role=role_de(u), tutelles=_compte(u)["tutelles"])
        return JsonResponse(_compte(u) | {"email_envoye": ok, "lien": None if ok else lien_mot_de_passe(u)},
                            status=201)
    return JsonResponse({"comptes": [_compte(u) for u in User.objects.filter(is_staff=True)
                                     .select_related("profil_equipe").order_by("-is_active", "last_name", "username")]})


@require_http_methods(["PUT", "POST"])
@equipe
def compte(request, pk):
    _exiger(request, "gerer_comptes")
    u = get_object_or_404(User, pk=pk, is_staff=True)
    if request.method == "POST":  # renvoyer le lien de (ré)initialisation
        ok = envoyer_lien_mot_de_passe(u, lien_mot_de_passe(u), nouveau_compte=not u.has_usable_password())
        tracer(request, "compte", u.get_username(), lien_envoye=ok)
        return JsonResponse({"email_envoye": ok, "lien": None if ok else lien_mot_de_passe(u)})
    avant = _compte(u)
    _appliquer_compte(u, _corps(request), request.user)
    apres = _compte(u)
    tracer(request, "compte", u.get_username(),
           changements={k: [avant[k], apres[k]] for k in ("role", "tutelles", "actif", "prenom", "nom")
                        if avant[k] != apres[k]})
    return JsonResponse(apres)


@require_GET
@equipe
def journal(request):
    _exiger(request, "voir_journal")
    qs = Journal.objects.all()
    if request.GET.get("action"):
        qs = qs.filter(action=request.GET["action"])
    if request.GET.get("q"):
        t = request.GET["q"]
        qs = qs.filter(Q(auteur__icontains=t) | Q(objet__icontains=t))
    page = Paginator(qs, 50).get_page(request.GET.get("page") or 1)
    return JsonResponse({
        "lignes": [{"id": j.pk, "date": j.date.isoformat(), "auteur": j.auteur, "action": j.action,
                    "libelle": LIBELLES.get(j.action, j.action), "objet": j.objet, "detail": j.detail, "ip": j.ip}
                   for j in page],
        "page": page.number, "pages": page.paginator.num_pages, "total": page.paginator.count,
        "actions": [{"valeur": k, "libelle": v} for k, v in LIBELLES.items()],
    })


CHAMPS_PARAMETRES = ["pays", "devise", "ministere", "institution", "monnaie", "email_contact", "texte_invitation",
                     "texte_relance", "signature"]


def _parametres(p):
    return {c: getattr(p, c) for c in CHAMPS_PARAMETRES} | {
        "logo": "/api/logo/" if p.logo else None,
        "smtp": {"hote": settings.EMAIL_HOST, "port": settings.EMAIL_PORT, "expediteur": settings.DEFAULT_FROM_EMAIL,
                 "tls": settings.EMAIL_USE_TLS},
        "defauts": {"pays": settings.PAYS, "devise": settings.DEVISE, "ministere": settings.NOM_MINISTERE,
                    "institution": settings.NOM_INSTITUTION}}


@require_http_methods(["GET", "POST"])
@equipe
def parametres(request):
    """F-48 : identité de l'institution, logo, textes des e-mails. Le serveur d'envoi se règle dans .env (secret)."""
    p = Parametres.charger()
    if request.method == "POST":
        _exiger(request, "parametrer")
        donnees = request.POST if request.content_type.startswith("multipart") else _corps(request)
        for c in CHAMPS_PARAMETRES:
            if c in donnees:
                setattr(p, c, str(donnees.get(c, ""))[:4000])
        if p.email_contact and "@" not in p.email_contact:
            raise Refus("L'e-mail d'assistance est invalide.")
        if "logo" in request.FILES:
            f = request.FILES["logo"]
            entete = f.read(8)
            f.seek(0)
            if f.size > 1024 * 1024 or not (entete.startswith(b"\x89PNG") or entete.startswith(b"\xff\xd8\xff")):
                raise Refus("Logo : image PNG ou JPG de 1 Mo au plus.")
            if p.logo:
                p.logo.delete(save=False)
            p.logo.save(f.name, f, save=False)
        if donnees.get("supprimer_logo") in ("1", True) and p.logo:
            p.logo.delete(save=False)
        p.save()
        tracer(request, "parametres", "Paramètres de l'application", champs=[c for c in CHAMPS_PARAMETRES if c in donnees])
    return JsonResponse(_parametres(p))
