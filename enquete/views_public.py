"""Parcours du répondant : lien reçu par e-mail → identification → modules → récapitulatif → envoi."""
from django.contrib import messages
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from .emails import envoyer_accuse
from .forms import CertificationForm, IdentificationForm, ModuleForm
from .models import Reponse
from .questionnaire import MODULES, libelle_reponse


def _charger(jeton):
    reponse = get_object_or_404(Reponse.objects.select_related("epn", "campagne"), jeton=jeton)
    return reponse


def _bloquee(request, reponse):
    """Page à afficher à la place du formulaire, ou None si la saisie est possible."""
    if reponse.est_soumise:
        return render(request, "enquete/public/deja_soumis.html", {"reponse": reponse})
    if not reponse.campagne.active or not reponse.campagne.est_ouverte:
        return render(request, "enquete/public/fermee.html", {"reponse": reponse}, status=403)
    return None


def _navigation(reponse, index_courant=None):
    return [
        {"code": m["code"], "titre": m["titre"], "fait": m["code"] in reponse.modules_completes,
         "courant": i == index_courant}
        for i, m in enumerate(MODULES)
    ]


@require_http_methods(["GET", "POST"])
def accueil(request, jeton):
    reponse = _charger(jeton)
    if (page := _bloquee(request, reponse)) is not None:
        return page
    initial = {} if reponse.email else {"email": reponse.epn.email_contact}
    form = IdentificationForm(request.POST or None, instance=reponse, initial=initial)
    if request.method == "POST" and form.is_valid():
        reponse = form.save(commit=False)
        if reponse.statut == Reponse.Statut.INVITE:
            reponse.statut = Reponse.Statut.EN_COURS
            reponse.date_debut = timezone.now()
        if not reponse.donnees.get("A01"):
            reponse.donnees["A01"] = reponse.epn.nom
            reponse.donnees["A02"] = reponse.epn.sigle
        reponse.save()
        return redirect("public:module", jeton=jeton, code=MODULES[0]["code"])
    return render(request, "enquete/public/accueil.html", {"reponse": reponse, "form": form,
                                                            "nb_modules": len(MODULES)})


@require_http_methods(["GET", "POST"])
def module(request, jeton, code):
    reponse = _charger(jeton)
    if (page := _bloquee(request, reponse)) is not None:
        return page
    if not reponse.nom:
        return redirect("public:accueil", jeton=jeton)
    index = next((i for i, m in enumerate(MODULES) if m["code"] == code), None)
    if index is None:
        return redirect("public:module", jeton=jeton, code=MODULES[0]["code"])
    mod = MODULES[index]

    if request.method == "POST":
        action = request.POST.get("action", "suivant")
        brouillon = action in ("brouillon", "precedent")
        form = ModuleForm(mod, request.POST, brouillon=brouillon)
        if form.is_valid():
            reponse.donnees.update(form.valeurs_json())
            # Un module n'est « complété » que s'il passe la validation complète (obligatoires + cohérence).
            complet = not brouillon or ModuleForm(mod, request.POST).is_valid()
            if complet and mod["code"] not in reponse.modules_completes:
                reponse.modules_completes.append(mod["code"])
            elif not complet and mod["code"] in reponse.modules_completes:
                reponse.modules_completes.remove(mod["code"])
            reponse.save()
            if action == "brouillon":
                messages.success(request, "Brouillon enregistré. Vous pouvez revenir plus tard avec le même lien.")
                return redirect("public:module", jeton=jeton, code=code)
            if action == "precedent":
                if index == 0:
                    return redirect("public:accueil", jeton=jeton)
                return redirect("public:module", jeton=jeton, code=MODULES[index - 1]["code"])
            if index + 1 < len(MODULES):
                return redirect("public:module", jeton=jeton, code=MODULES[index + 1]["code"])
            return redirect("public:recapitulatif", jeton=jeton)
        messages.error(request, "Certaines réponses sont à corriger avant de continuer.")
    else:
        form = ModuleForm(mod, initial={q["code"]: reponse.donnees.get(q["code"]) for q in mod["questions"]})

    return render(request, "enquete/public/module.html", {
        "reponse": reponse, "module": mod, "form": form, "index": index + 1, "total": len(MODULES),
        "navigation": _navigation(reponse, index), "avancement": reponse.avancement(),
        "dernier": index + 1 == len(MODULES),
    })


def _recapitulatif(reponse):
    return [
        {"module": m, "fait": m["code"] in reponse.modules_completes,
         "lignes": [(q, libelle_reponse(q, reponse.donnees.get(q["code"]))) for q in m["questions"]]}
        for m in MODULES
    ]


@require_http_methods(["GET", "POST"])
def recapitulatif(request, jeton):
    reponse = _charger(jeton)
    if (page := _bloquee(request, reponse)) is not None:
        return page
    if not reponse.nom:
        return redirect("public:accueil", jeton=jeton)
    manquants = [m for m in MODULES if m["code"] not in reponse.modules_completes]
    form = CertificationForm(request.POST or None)
    if request.method == "POST":
        if manquants:
            messages.error(request, "Tous les modules doivent être complétés avant l'envoi.")
        elif form.is_valid():
            with transaction.atomic():
                reponse = Reponse.objects.select_for_update().get(pk=reponse.pk)
                if not reponse.est_soumise:
                    reponse.statut = Reponse.Statut.SOUMIS
                    reponse.date_soumission = timezone.now()
                    reponse.save(update_fields=["statut", "date_soumission", "date_modification"])
            envoyer_accuse(reponse)
            return redirect("public:merci", jeton=jeton)
    return render(request, "enquete/public/recapitulatif.html", {
        "reponse": reponse, "recap": _recapitulatif(reponse), "manquants": manquants, "form": form,
        "navigation": _navigation(reponse), "avancement": reponse.avancement(),
    })


def merci(request, jeton):
    reponse = _charger(jeton)
    return render(request, "enquete/public/merci.html", {"reponse": reponse, "recap": _recapitulatif(reponse)})


def page_accueil(request):
    return render(request, "enquete/public/sans_lien.html")
