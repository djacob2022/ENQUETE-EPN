from decimal import Decimal

from django import forms
from django.core.validators import MaxValueValidator, MinValueValidator

from .models import EPN, Campagne, Reponse
from .pieces import ACCEPT, LIBELLE_FORMATS, valider_piece
from .questionnaire import OUI_NON, REGLES_COHERENCE


class IdentificationForm(forms.ModelForm):
    class Meta:
        model = Reponse
        fields = ["nom", "prenom", "fonction", "email", "telephone"]
        labels = {"email": "Adresse e-mail", "fonction": "Fonction dans l'établissement"}
        widgets = {
            "nom": forms.TextInput(attrs={"autocomplete": "family-name"}),
            "prenom": forms.TextInput(attrs={"autocomplete": "given-name"}),
            "email": forms.EmailInput(attrs={"autocomplete": "email"}),
            "telephone": forms.TextInput(attrs={"autocomplete": "tel", "inputmode": "tel"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for champ in self.fields.values():
            champ.required = True

    def clean_telephone(self):
        tel = self.cleaned_data["telephone"].strip()
        chiffres = [c for c in tel if c.isdigit()]
        if len(chiffres) < 8:
            raise forms.ValidationError("Numéro de téléphone incomplet (8 chiffres au moins).")
        return tel


def _champ(q, brouillon, deja_depose=False):
    # Une pièce déjà déposée satisfait l'obligation : on ne redemande pas le fichier.
    requis = q.get("obligatoire", True) and not brouillon and not deja_depose
    aide = q.get("aide", "") or (f"En {q['unite']}." if q.get("unite") else "")
    commun = {"label": f"{q['code']} · {q['libelle']}", "required": requis, "help_text": aide}
    t = q["type"]
    if t == "texte":
        return forms.CharField(max_length=500, **commun)
    if t == "texte_long":
        return forms.CharField(max_length=5000, widget=forms.Textarea(attrs={"rows": 4}), **commun)
    if t == "url":
        return forms.URLField(assume_scheme="https", **commun)
    if t == "entier":
        validateurs = []
        if "min" in q:
            validateurs.append(MinValueValidator(q["min"]))
        if "max" in q:
            validateurs.append(MaxValueValidator(q["max"]))
        return forms.IntegerField(validators=validateurs, widget=forms.NumberInput(attrs={"inputmode": "numeric"}), **commun)
    if t == "montant":
        return forms.DecimalField(max_digits=18, decimal_places=2, min_value=Decimal("0"),
                                  widget=forms.NumberInput(attrs={"step": "0.01", "inputmode": "decimal"}), **commun)
    if t == "pourcentage":
        return forms.DecimalField(max_digits=5, decimal_places=2, min_value=Decimal("0"), max_value=Decimal("100"),
                                  widget=forms.NumberInput(attrs={"step": "0.1"}), **commun)
    if t == "oui_non":
        return forms.ChoiceField(choices=OUI_NON, widget=forms.RadioSelect, **commun)
    if t == "choix":
        return forms.ChoiceField(choices=q["choix"], widget=forms.RadioSelect, **commun)
    if t == "choix_multiple":
        return forms.MultipleChoiceField(choices=q["choix"], widget=forms.CheckboxSelectMultiple, **commun)
    if t == "fichier":
        commun["help_text"] = commun["help_text"] or f"{LIBELLE_FORMATS} · 10 Mo maximum."
        return forms.FileField(validators=[valider_piece], widget=forms.FileInput(attrs={"accept": ACCEPT}), **commun)
    raise ValueError(f"Type de question inconnu : {t}")


def vers_json(valeur):
    """Convertit une valeur nettoyée en valeur stockable dans le JSON de la réponse."""
    if isinstance(valeur, Decimal):
        return int(valeur) if valeur == valeur.to_integral_value() else float(valeur)
    if valeur == "":
        return None
    return valeur


class ModuleForm(forms.Form):
    """Formulaire construit à partir d'un module du questionnaire.

    En mode brouillon, rien n'est obligatoire et les règles de cohérence ne bloquent pas :
    la personne peut enregistrer et revenir plus tard.
    """

    def __init__(self, module, *args, brouillon=False, pieces=None, **kwargs):
        """`pieces` : pièces jointes déjà déposées pour cette réponse, par code de question."""
        super().__init__(*args, **kwargs)
        self.module = module
        self.brouillon = brouillon
        pieces = pieces or {}
        for q in module["questions"]:
            champ = _champ(q, brouillon, deja_depose=q["code"] in pieces)
            # Les textes longs et les listes de choix occupent toute la largeur ; les nombres vont par deux.
            champ.pleine_largeur = q["type"] in ("texte_long", "choix", "choix_multiple", "texte", "url", "fichier")
            champ.piece = pieces.get(q["code"])
            champ.obligatoire = q.get("obligatoire", True)
            self.fields[q["code"]] = champ

    def clean(self):
        donnees = super().clean()
        if self.brouillon:
            return donnees
        for champs, regle in REGLES_COHERENCE.get(self.module["code"], []):
            message = regle(donnees)
            if message:
                for code in champs:
                    self.add_error(code, message)
        return donnees

    def valeurs_json(self):
        """Valeurs à stocker, hors fichiers (enregistrés à part par `fichiers_deposes`)."""
        return {code: vers_json(v) for code, v in self.cleaned_data.items()
                if not isinstance(self.fields[code], forms.FileField)}

    def fichiers_deposes(self):
        return {code: f for code, f in self.cleaned_data.items()
                if isinstance(self.fields[code], forms.FileField) and f}


class CertificationForm(forms.Form):
    certification = forms.BooleanField(
        label="Je certifie l'exactitude et l'exhaustivité des informations transmises.", required=True
    )


class InvitationForm(forms.Form):
    epn = forms.ModelMultipleChoiceField(
        queryset=EPN.objects.filter(actif=True), widget=forms.CheckboxSelectMultiple, required=False,
        label="EPN à inviter",
    )


class CampagneForm(forms.ModelForm):
    class Meta:
        model = Campagne
        fields = ["nom", "exercice", "date_ouverture", "date_cloture", "active"]
        widgets = {"date_ouverture": forms.DateInput(attrs={"type": "date"}),
                   "date_cloture": forms.DateInput(attrs={"type": "date"})}

    def clean(self):
        d = super().clean()
        if d.get("date_ouverture") and d.get("date_cloture") and d["date_cloture"] < d["date_ouverture"]:
            self.add_error("date_cloture", "La clôture doit suivre l'ouverture.")
        return d


class ImportEPNForm(forms.Form):
    fichier = forms.FileField(
        label="Fichier Excel (.xlsx)",
        help_text="Colonnes attendues, dans cet ordre : Dénomination, Sigle, Catégorie (EPA/EPIC/AUTRE), "
                  "Tutelle, Région, E-mail du point focal. Première ligne = en-têtes.",
    )

    def clean_fichier(self):
        f = self.cleaned_data["fichier"]
        if not f.name.lower().endswith(".xlsx"):
            raise forms.ValidationError("Seuls les fichiers .xlsx sont acceptés.")
        if f.size > 5 * 1024 * 1024:
            raise forms.ValidationError("Fichier trop volumineux (5 Mo maximum).")
        return f
