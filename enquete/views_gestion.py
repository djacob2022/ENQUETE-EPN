"""Espace administrateur : suivi, invitations, relances, consultation, export Excel, statistiques."""
import zipfile
from io import BytesIO

from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.db import transaction
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.text import get_valid_filename
from django.views.decorators.http import require_POST

from . import export_excel, statistiques
from .emails import envoyer_invitation, envoyer_relance
from .forms import CampagneForm, ImportEPNForm
from .views_public import reponse_fichier
from .models import EPN, Campagne, PieceJointe, Reponse
from .questionnaire import MODULES, affichage

# Réservé aux comptes « équipe » ; les autres sont renvoyés vers la page de connexion de l'application.
staff_member_required = user_passes_test(lambda u: u.is_active and u.is_staff, login_url="login")


def _campagne(request):
    cid = request.GET.get("campagne") or request.POST.get("campagne")
    if cid:
        return get_object_or_404(Campagne, pk=cid)
    return Campagne.courante() or Campagne.objects.first()


def _filtrer(request, qs):
    f = request.GET
    if f.get("statut"):
        qs = qs.filter(statut=f["statut"])
    if f.get("tutelle"):
        qs = qs.filter(epn__tutelle=f["tutelle"])
    if f.get("categorie"):
        qs = qs.filter(epn__categorie=f["categorie"])
    if f.get("region"):
        qs = qs.filter(epn__region=f["region"])
    if f.get("q"):
        qs = qs.filter(Q(epn__nom__icontains=f["q"]) | Q(epn__sigle__icontains=f["q"]) | Q(nom__icontains=f["q"]))
    return qs


def _contexte_filtres(request, campagne):
    return {
        "campagnes": Campagne.objects.all(),
        "campagne": campagne,
        "tutelles": EPN.objects.order_by("tutelle").values_list("tutelle", flat=True).distinct(),
        "regions": EPN.objects.exclude(region="").order_by("region").values_list("region", flat=True).distinct(),
        "categories": EPN.Categorie.choices,
        "statuts": Reponse.Statut.choices,
        "f": request.GET,
    }


def _sans_campagne(request):
    messages.info(request, "Créez d'abord une campagne.")
    return redirect("gestion:campagne_nouvelle")


@staff_member_required
def tableau_de_bord(request):
    campagne = _campagne(request)
    if campagne is None:
        return _sans_campagne(request)
    reponses = list(_filtrer(request, campagne.reponses.select_related("epn")))
    compte = {s: 0 for s, _ in Reponse.Statut.choices}
    for r in reponses:
        compte[r.statut] += 1
    invites = len(reponses)
    soumises = [r for r in reponses if r.est_soumise]
    ctx = _contexte_filtres(request, campagne) | {
        "invites": invites,
        "compte": compte,
        "taux": round(100 * len(soumises) / invites) if invites else 0,
        "non_invites": EPN.objects.filter(actif=True).exclude(reponses__campagne=campagne).count(),
        "effectif_total": sum(r.donnees.get("D01") or 0 for r in soumises),
        "par_tutelle": statistiques.taux_par_groupe(reponses, "tutelle"),
        "par_categorie": statistiques.taux_par_groupe(reponses, "categorie"),
        "retardataires": [r for r in reponses if not r.est_soumise][:10],
        "nb_retardataires": invites - len(soumises),
        "dernieres": sorted(soumises, key=lambda r: r.date_soumission, reverse=True)[:5],
        "indicateurs": statistiques.indicateurs(soumises),
    }
    return render(request, "enquete/gestion/tableau_de_bord.html", ctx)


@staff_member_required
def reponses(request):
    campagne = _campagne(request)
    if campagne is None:
        return _sans_campagne(request)
    qs = _filtrer(request, campagne.reponses.select_related("epn")).order_by("statut", "epn__nom")
    return render(request, "enquete/gestion/reponses.html",
                  _contexte_filtres(request, campagne) | {"reponses": qs})


@staff_member_required
def reponse_detail(request, pk):
    reponse = get_object_or_404(Reponse.objects.select_related("epn", "campagne"), pk=pk)
    recap = [{"module": m, "fait": m["code"] in reponse.modules_completes,
              "lignes": [(q, affichage(q, reponse.donnees.get(q["code"]))) for q in m["questions"]]}
             for m in MODULES]
    return render(request, "enquete/gestion/reponse_detail.html",
                  {"reponse": reponse, "recap": recap, "envois": reponse.envois.all()[:20],
                   "pieces": {p.code: p for p in reponse.pieces.all()}})


@staff_member_required
def piece(request, pk):
    return reponse_fichier(get_object_or_404(PieceJointe, pk=pk))


@staff_member_required
def pieces_zip(request, pk):
    """Toutes les pièces d'une réponse dans une archive ZIP."""
    reponse = get_object_or_404(Reponse.objects.select_related("epn"), pk=pk)
    tampon = BytesIO()
    with zipfile.ZipFile(tampon, "w", zipfile.ZIP_DEFLATED) as archive:
        for p in reponse.pieces.all():
            try:
                with p.fichier.open("rb") as f:
                    archive.writestr(f"{p.code}_{get_valid_filename(p.nom_original)}", f.read())
            except FileNotFoundError:
                continue
    resp = HttpResponse(tampon.getvalue(), content_type="application/zip")
    nom = get_valid_filename(reponse.epn.sigle or reponse.epn.nom)
    resp["Content-Disposition"] = f'attachment; filename="pieces_{nom}_{reponse.campagne.exercice}.zip"'
    return resp


@staff_member_required
@require_POST
def reponse_rouvrir(request, pk):
    reponse = get_object_or_404(Reponse, pk=pk)
    if reponse.est_soumise:
        reponse.statut = Reponse.Statut.EN_COURS
        reponse.date_soumission = None
        reponse.save(update_fields=["statut", "date_soumission", "date_modification"])
        messages.success(request, f"La réponse de {reponse.epn.nom} est rouverte : l'EPN peut la corriger avec son lien.")
    return redirect("gestion:reponse_detail", pk=pk)


@staff_member_required
@require_POST
def relancer(request, pk):
    reponse = get_object_or_404(Reponse.objects.select_related("epn", "campagne"), pk=pk)
    if envoyer_relance(reponse, par=request.user.get_username()):
        messages.success(request, f"Relance envoyée à {reponse.epn.nom}.")
    else:
        messages.error(request, f"La relance de {reponse.epn.nom} n'a pas pu être envoyée.")
    suivant = request.POST.get("suivant", "")
    if url_has_allowed_host_and_scheme(suivant, allowed_hosts={request.get_host()}):
        return redirect(suivant)
    return redirect("gestion:reponses")


@staff_member_required
@require_POST
def relancer_retardataires(request):
    campagne = _campagne(request)
    cibles = campagne.reponses.select_related("epn", "campagne").exclude(statut=Reponse.Statut.SOUMIS)
    ok = sum(envoyer_relance(r, par=request.user.get_username()) for r in cibles)
    total = cibles.count()
    if ok == total:
        messages.success(request, f"{ok} relance(s) envoyée(s).")
    else:
        messages.warning(request, f"{ok} relance(s) envoyée(s) sur {total} : consultez l'historique des envois.")
    return redirect("gestion:tableau_de_bord")


@staff_member_required
def invitations(request):
    campagne = _campagne(request)
    if campagne is None:
        return _sans_campagne(request)
    non_invites = EPN.objects.filter(actif=True).exclude(reponses__campagne=campagne)
    if request.method == "POST":
        ids = request.POST.getlist("epn")
        cibles = non_invites.filter(pk__in=ids) if ids else non_invites
        ok = 0
        for epn in cibles:
            with transaction.atomic():
                reponse, _ = Reponse.objects.get_or_create(campagne=campagne, epn=epn)
            ok += envoyer_invitation(reponse, par=request.user.get_username())
        messages.success(request, f"{ok} invitation(s) envoyée(s) avec un lien personnel.")
        return redirect("gestion:reponses")
    return render(request, "enquete/gestion/invitations.html",
                  {"campagne": campagne, "non_invites": non_invites,
                   "invites": campagne.reponses.select_related("epn").order_by("epn__nom")})


@staff_member_required
def liens(request):
    """Le lien personnel de chaque EPN, à copier ou à exporter pour un envoi depuis sa propre messagerie."""
    campagne = _campagne(request)
    if campagne is None:
        return _sans_campagne(request)
    if request.method == "POST":
        crees = campagne.generer_liens()
        messages.success(request, f"{crees} lien(s) généré(s)." if crees else "Tous les EPN actifs ont déjà un lien.")
        return redirect(f"{request.path}?campagne={campagne.pk}")
    reponses = campagne.reponses.select_related("epn").order_by("epn__nom")
    if request.GET.get("format") == "xlsx":
        contenu = export_excel.classeur_liens(campagne, reponses)
        resp = HttpResponse(contenu, content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        resp["Content-Disposition"] = f'attachment; filename="liens_EPN_{campagne.exercice}.xlsx"'
        return resp
    sans_lien = EPN.objects.filter(actif=True).exclude(reponses__campagne=campagne).count()
    return render(request, "enquete/gestion/liens.html",
                  {"campagne": campagne, "campagnes": Campagne.objects.all(), "reponses": reponses,
                   "sans_lien": sans_lien})


@staff_member_required
@require_POST
def reinviter(request, pk):
    reponse = get_object_or_404(Reponse.objects.select_related("epn", "campagne"), pk=pk)
    envoyer_invitation(reponse, par=request.user.get_username())
    messages.success(request, f"Invitation renvoyée à {reponse.epn.nom}.")
    return redirect("gestion:reponse_detail", pk=pk)


@staff_member_required
def export(request):
    campagne = _campagne(request)
    if campagne is None:
        return _sans_campagne(request)
    qs = _filtrer(request, campagne.reponses.select_related("epn"))
    if request.GET.get("toutes") != "1" and not request.GET.get("statut"):
        qs = qs.filter(statut=Reponse.Statut.SOUMIS)
    contenu = export_excel.classeur(campagne, list(qs.order_by("epn__nom")))
    resp = HttpResponse(contenu, content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    resp["Content-Disposition"] = f'attachment; filename="{export_excel.nom_fichier(campagne)}"'
    return resp


@staff_member_required
def stats(request):
    campagne = _campagne(request)
    if campagne is None:
        return _sans_campagne(request)
    qs = _filtrer(request, campagne.reponses.select_related("epn"))
    if request.GET.get("toutes") != "1":
        qs = qs.filter(statut=Reponse.Statut.SOUMIS)
    rep = list(qs)
    return render(request, "enquete/gestion/statistiques.html", _contexte_filtres(request, campagne) | {
        "n": len(rep), "blocs": statistiques.par_question(rep), "indicateurs": statistiques.indicateurs(rep),
        "historique": _historique(),
    })


def _historique():
    lignes = []
    for c in Campagne.objects.order_by("exercice").annotate(
        total=Count("reponses"), soumis=Count("reponses", filter=Q(reponses__statut=Reponse.Statut.SOUMIS))
    ).filter(total__gt=0):
        lignes.append({"libelle": str(c.exercice), "taux": round(100 * c.soumis / c.total) if c.total else 0})
    return lignes


@staff_member_required
def epn_liste(request):
    form = ImportEPNForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        lignes, erreurs = export_excel.lire_epn(form.cleaned_data["fichier"])
        crees = maj = 0
        for ligne in lignes:
            _, cree = EPN.objects.update_or_create(nom=ligne.pop("nom"), defaults=ligne)
            crees += cree
            maj += not cree
        messages.success(request, f"Import terminé : {crees} EPN créé(s), {maj} mis à jour.")
        for e in erreurs[:20]:
            messages.warning(request, e)
        return redirect("gestion:epn")
    qs = EPN.objects.all()
    if request.GET.get("q"):
        qs = qs.filter(Q(nom__icontains=request.GET["q"]) | Q(sigle__icontains=request.GET["q"]))
    return render(request, "enquete/gestion/epn.html", {"epns": qs, "form": form, "f": request.GET})


@staff_member_required
def campagnes(request):
    return render(request, "enquete/gestion/campagnes.html", {
        "campagnes": Campagne.objects.annotate(
            total=Count("reponses"), soumis=Count("reponses", filter=Q(reponses__statut=Reponse.Statut.SOUMIS)))
    })


@staff_member_required
def campagne_form(request, pk=None):
    instance = get_object_or_404(Campagne, pk=pk) if pk else None
    form = CampagneForm(request.POST or None, instance=instance)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Campagne enregistrée.")
        return redirect("gestion:campagnes")
    return render(request, "enquete/gestion/campagne_form.html", {"form": form, "instance": instance})


@staff_member_required
def questionnaire_apercu(request):
    """Le questionnaire complet, imprimable : le formulaire type adressé aux EPN."""
    return render(request, "enquete/gestion/questionnaire.html", {"modules": MODULES})
