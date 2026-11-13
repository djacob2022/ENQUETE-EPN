import secrets

from django.conf import settings
from django.db import models
from django.utils import timezone


def lien_public():
    """Le lien unique, identique pour tous les EPN (seul endroit où il est construit)."""
    from django.conf import settings

    return settings.SITE_URL + "/formulaire"


def nouveau_jeton():
    return secrets.token_urlsafe(24)


class ListeReference(models.Model):
    """Listes de référence du répertoire (F-08) : ministères de tutelle, régions, secteurs."""

    class Type(models.TextChoices):
        TUTELLE = "tutelle", "Ministère de tutelle"
        REGION = "region", "Région"
        SECTEUR = "secteur", "Secteur d'activité"

    type = models.CharField(max_length=10, choices=Type.choices)
    libelle = models.CharField("libellé", max_length=255)

    class Meta:
        ordering = ["type", "libelle"]
        verbose_name = "liste de référence"
        constraints = [models.UniqueConstraint(fields=["type", "libelle"], name="libelle_unique_par_liste")]

    def __str__(self):
        return f"{self.get_type_display()} · {self.libelle}"


class EPN(models.Model):
    class Categorie(models.TextChoices):
        EPA = "EPA", "EPA"
        EPIC = "EPIC", "EPIC"
        AUTRE = "AUTRE", "Autre"

    class Etat(models.TextChoices):
        ACTIF = "actif", "Actif"
        LIQUIDATION = "liquidation", "En liquidation"
        DISSOUS = "dissous", "Dissous"

    nom = models.CharField("dénomination", max_length=255, unique=True)
    sigle = models.CharField(max_length=50, blank=True)
    categorie = models.CharField("catégorie", max_length=10, choices=Categorie.choices, default=Categorie.EPA)
    tutelle = models.CharField("tutelle technique", max_length=255)
    region = models.CharField("région", max_length=120, blank=True)
    secteur = models.CharField("secteur d'activité", max_length=120, blank=True)
    email_contact = models.EmailField("e-mail du point focal")
    etat = models.CharField("statut", max_length=12, choices=Etat.choices, default=Etat.ACTIF)
    actif = models.BooleanField(default=True, help_text="Calculé : seuls les EPN actifs sont interrogés.")
    date_modification = models.DateTimeField(auto_now=True, null=True)

    class Meta:
        ordering = ["nom"]
        verbose_name = "EPN"
        verbose_name_plural = "EPN"

    def __str__(self):
        return f"{self.nom} ({self.sigle})" if self.sigle else self.nom

    @classmethod
    def from_db(cls, db, field_names, values):
        instance = super().from_db(db, field_names, values)
        instance._actif_initial = getattr(instance, "actif", True)
        return instance

    def save(self, *args, **kwargs):
        # « actif » suit le statut ; un code qui ne règle que « actif » (ancien usage) fixe le statut en conséquence.
        if not self.actif and self.etat == self.Etat.ACTIF and getattr(self, "_actif_initial", True):
            self.etat = self.Etat.DISSOUS
        self.actif = self.etat == self.Etat.ACTIF
        self._actif_initial = self.actif
        if kwargs.get("update_fields") is not None and "etat" in kwargs["update_fields"]:
            kwargs["update_fields"] = list(kwargs["update_fields"]) + ["actif"]
        super().save(*args, **kwargs)


def _definition_par_defaut():
    from .questionnaire import definition_par_defaut

    return definition_par_defaut()


def _csv(texte):
    return [t.strip() for t in (texte or "").split(",") if t.strip()]


class Campagne(models.Model):
    nom = models.CharField(max_length=200)
    exercice = models.PositiveIntegerField("exercice de référence")
    date_ouverture = models.DateField()
    date_cloture = models.DateField("date de clôture")
    active = models.BooleanField(
        default=True, help_text="Une seule campagne active : celle que voient les liens envoyés aux EPN."
    )
    questionnaire = models.JSONField(
        default=_definition_par_defaut,
        help_text="Questionnaire de la campagne (modules, questions, règles), versionné et modifiable dans l'éditeur.")
    cible_tutelles = models.CharField(
        "tutelles ciblées", max_length=1000, blank=True, help_text="Séparées par des virgules. Vide = toutes.")
    cible_categories = models.CharField("catégories ciblées", max_length=100, blank=True, help_text="Vide = toutes.")
    relances_auto = models.CharField(
        "relances automatiques", max_length=60, blank=True, default="-7,-2,1",
        help_text="Jours par rapport à la clôture (ex. « -7,-2,1 » = J-7, J-2 et J+1). Vide = aucune.")

    class Meta:
        ordering = ["-date_ouverture"]

    def __str__(self):
        return self.nom

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.active:
            Campagne.objects.exclude(pk=self.pk).filter(active=True).update(active=False)

    @classmethod
    def courante(cls):
        return cls.objects.filter(active=True).first()

    @property
    def q(self):
        from .langue import anglais
        from .questionnaire import Questionnaire

        q = Questionnaire(self.questionnaire)
        return q.en_anglais() if anglais() else q  # parcours du répondant en anglais (F-16)

    @property
    def liste_cible_tutelles(self):
        return _csv(self.cible_tutelles)

    @property
    def liste_cible_categories(self):
        return _csv(self.cible_categories)

    @property
    def jours_relance(self):
        jours = []
        for t in _csv(self.relances_auto):
            try:
                jours.append(int(t))
            except ValueError:
                continue
        return sorted(set(jours))

    def epn_cibles(self, epns=None):
        """EPN actifs visés par la campagne (F-17)."""
        epns = EPN.objects.filter(actif=True) if epns is None else epns
        if self.liste_cible_tutelles:
            epns = epns.filter(tutelle__in=self.liste_cible_tutelles)
        if self.liste_cible_categories:
            epns = epns.filter(categorie__in=self.liste_cible_categories)
        return epns

    def generer_liens(self, epns=None):
        """Crée le lien personnel (une Reponse) de chaque EPN ciblé qui n'en a pas encore. Renvoie le nombre créé."""
        epns = self.epn_cibles(epns)
        crees = 0
        for epn in epns.exclude(reponses__campagne=self):
            _, cree = Reponse.objects.get_or_create(campagne=self, epn=epn)
            crees += cree
        return crees

    @property
    def est_ouverte(self):
        aujourd_hui = timezone.localdate()
        return self.date_ouverture <= aujourd_hui <= self.date_cloture


class Reponse(models.Model):
    """La réponse d'un EPN à une campagne. Créée à l'envoi de l'invitation, avec un lien personnel."""

    class Statut(models.TextChoices):
        """Circuit de la réponse (F-29) : brouillon → soumis → en revue → validé, ou renvoyé « à corriger »."""
        INVITE = "invite", "Invité, non commencé"
        EN_COURS = "en_cours", "Brouillon"
        SOUMIS = "soumis", "Soumis"
        EN_REVUE = "en_revue", "En revue"
        A_CORRIGER = "a_corriger", "À corriger"
        VALIDE = "valide", "Validé"

    ENVOYES = ("soumis", "en_revue", "valide")  # réponses transmises par l'EPN (comptent dans le taux de réponse)

    campagne = models.ForeignKey(Campagne, on_delete=models.CASCADE, related_name="reponses")
    epn = models.ForeignKey(EPN, on_delete=models.CASCADE, related_name="reponses")
    jeton = models.CharField(max_length=64, unique=True, default=nouveau_jeton, editable=False)
    statut = models.CharField(max_length=10, choices=Statut.choices, default=Statut.INVITE)
    langue = models.CharField("langue du répondant", max_length=2, default="fr",
                              choices=[("fr", "Français"), ("en", "English")])

    # Identification du répondant, saisie à l'ouverture du lien.
    nom = models.CharField(max_length=120, blank=True)
    prenom = models.CharField("prénom", max_length=120, blank=True)
    fonction = models.CharField(max_length=160, blank=True)
    email = models.EmailField(blank=True)
    telephone = models.CharField("téléphone", max_length=40, blank=True)

    donnees = models.JSONField(default=dict, blank=True)
    modules_completes = models.JSONField(default=list, blank=True)

    date_invitation = models.DateTimeField(null=True, blank=True)
    date_derniere_relance = models.DateTimeField(null=True, blank=True)
    nombre_relances = models.PositiveIntegerField(default=0)
    date_debut = models.DateTimeField(null=True, blank=True)
    date_modification = models.DateTimeField(auto_now=True)
    date_soumission = models.DateTimeField(null=True, blank=True)
    date_validation = models.DateTimeField(null=True, blank=True)
    valide_par = models.CharField(max_length=150, blank=True)
    date_limite = models.DateField(
        "délai accordé", null=True, blank=True, help_text="Prolongation pour cet EPN (F-20). Vide = date de clôture.")
    commentaires = models.JSONField(
        default=dict, blank=True,
        help_text="Commentaires de correction : {code de question: texte, « general »: texte} (F-30).")

    class Meta:
        ordering = ["epn__nom"]
        constraints = [models.UniqueConstraint(fields=["campagne", "epn"], name="une_reponse_par_epn_et_campagne")]

    def __str__(self):
        return f"{self.epn} – {self.campagne}"

    @property
    def lien(self):
        from django.conf import settings
        from django.urls import reverse

        return settings.SITE_URL + reverse("public:accueil", args=[self.jeton])

    @property
    def est_soumise(self):
        """Transmise par l'EPN (soumise, en revue ou validée) : plus modifiable par le répondant."""
        return self.statut in self.ENVOYES

    @property
    def est_validee(self):
        return self.statut == self.Statut.VALIDE

    @property
    def date_limite_effective(self):
        return max(self.date_limite, self.campagne.date_cloture) if self.date_limite else self.campagne.date_cloture

    @property
    def repondant(self):
        return f"{self.prenom} {self.nom}".strip()

    def remplacer_lien(self):
        """Nouveau jeton : l'ancien lien cesse immédiatement de fonctionner (lien transféré, ancien agent…)."""
        self.jeton = nouveau_jeton()
        self.save(update_fields=["jeton", "date_modification"])

    def avancement(self):
        codes = self.campagne.q.codes_modules()
        if not codes:
            return 0
        return round(100 * len(set(self.modules_completes) & set(codes)) / len(codes))


class DemandeAcces(models.Model):
    """Une demande de lien sur le formulaire public, pour la limite anti-abus par adresse IP."""

    ip = models.GenericIPAddressField(db_index=True)
    date = models.DateTimeField(auto_now_add=True, db_index=True)


class EchecConnexion(models.Model):
    """Un mot de passe erroné : sert au blocage temporaire contre la force brute."""

    identifiant = models.CharField(max_length=150, db_index=True)
    ip = models.GenericIPAddressField(db_index=True)
    date = models.DateTimeField(auto_now_add=True, db_index=True)


class ProfilEquipe(models.Model):
    """Rôle et périmètre d'un compte de l'équipe (section 3 du cahier des charges).

    Sans profil, le compte est administrateur d'enquête. Une liste de tutelles restreint les établissements visibles.
    """

    class Role(models.TextChoices):
        ADMINISTRATEUR = "administrateur", "Administrateur d'enquête"
        SUPERVISEUR = "superviseur", "Superviseur de tutelle"
        ANALYSTE = "analyste", "Analyste"
        LECTEUR = "lecteur", "Lecteur"

    utilisateur = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profil_equipe")
    role = models.CharField("rôle", max_length=15, choices=Role.choices, default=Role.ADMINISTRATEUR)
    tutelles = models.CharField(
        "tutelles", max_length=1000, blank=True,
        help_text="Tutelles techniques visibles, séparées par des virgules (ex. « Santé, Éducation »). "
                  "Vide = tous les établissements.")

    class Meta:
        verbose_name = "profil d'équipe"

    def __str__(self):
        return f"{self.utilisateur} · {self.tutelles or 'toutes tutelles'}"

    @property
    def liste_tutelles(self):
        return [t.strip() for t in self.tutelles.split(",") if t.strip()]


# Ce que chaque rôle peut faire. Le super-administrateur (is_superuser) a tous les droits, comptes et journal compris.
PERMISSIONS = {
    "administrateur": {"voir_nominatif", "exporter", "valider", "relancer", "gerer_liens", "gerer_campagnes",
                       "gerer_questionnaire", "gerer_repertoire", "voir_journal", "gerer_comptes", "parametrer"},
    "superviseur": {"voir_nominatif", "exporter", "valider", "relancer", "gerer_liens"},
    "analyste": {"voir_nominatif", "exporter"},
    "lecteur": set(),
}


def role_de(user):
    if user.is_superuser:
        return "super_administrateur"
    profil = getattr(user, "profil_equipe", None)
    return profil.role if profil else ProfilEquipe.Role.ADMINISTRATEUR


def permissions_de(user):
    role = role_de(user)
    if role == "super_administrateur":
        return set().union(*PERMISSIONS.values())
    perms = set(PERMISSIONS.get(role, set()))
    if tutelles_autorisees(user) is not None:
        # Un compte limité à certaines tutelles ne touche pas aux réglages communs à toutes.
        perms -= {"gerer_campagnes", "gerer_questionnaire", "gerer_repertoire", "voir_journal", "gerer_comptes",
                  "parametrer"}
    return perms


def tutelles_autorisees(user):
    """None = accès à tous les établissements ; sinon la liste des tutelles visibles."""
    if user.is_superuser:
        return None
    profil = getattr(user, "profil_equipe", None)  # l'absence de profil lève une AttributeError, rattrapée ici
    return (profil.liste_tutelles or None) if profil else None


class Envoi(models.Model):
    """Journal des e-mails envoyés (invitations et relances)."""

    class Type(models.TextChoices):
        INVITATION = "invitation", "Invitation"
        RELANCE = "relance", "Relance"
        ACCUSE = "accuse", "Accusé de réception"
        ACCES = "acces", "Lien demandé via le formulaire public"
        NOUVEAU_LIEN = "nouveau_lien", "Nouveau lien (l'ancien est révoqué)"
        CORRECTION = "correction", "Demande de correction"
        VALIDATION = "validation", "Réponse validée"

    reponse = models.ForeignKey(Reponse, on_delete=models.CASCADE, related_name="envois")
    type = models.CharField(max_length=12, choices=Type.choices)
    destinataires = models.CharField(max_length=500)
    date = models.DateTimeField(auto_now_add=True)
    succes = models.BooleanField(default=True)
    erreur = models.TextField(blank=True)
    par = models.CharField(max_length=150, blank=True)

    class Meta:
        ordering = ["-date"]


def chemin_piece(instance, nom_fichier):
    """Chemin de stockage : jamais le nom fourni par l'utilisateur, seulement son extension."""
    import os
    import uuid

    extension = os.path.splitext(nom_fichier)[1].lower()
    r = instance.reponse
    return f"pieces/{r.campagne_id}/{r.epn_id}/{instance.code}_{uuid.uuid4().hex}{extension}"


class PieceJointe(models.Model):
    """Fichier déposé pour une question de type « fichier » (une pièce par question)."""

    reponse = models.ForeignKey(Reponse, on_delete=models.CASCADE, related_name="pieces")
    code = models.CharField("question", max_length=10)
    fichier = models.FileField(upload_to=chemin_piece, max_length=255)
    nom_original = models.CharField(max_length=255)
    taille = models.PositiveIntegerField("taille (octets)")
    date_depot = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["code"]
        verbose_name = "pièce jointe"
        constraints = [models.UniqueConstraint(fields=["reponse", "code"], name="une_piece_par_question")]

    def __str__(self):
        return f"{self.code} · {self.nom_original}"

    def supprimer(self):
        self.fichier.delete(save=False)
        self.delete()


class Journal(models.Model):
    """Journal d'audit (F-46) : qui a fait quoi et quand. Les lignes ne sont jamais modifiées ni supprimées
    par l'application ; elles sont conservées au moins 3 ans (section 7)."""

    date = models.DateTimeField(auto_now_add=True, db_index=True)
    auteur = models.CharField(max_length=150, blank=True, help_text="Identifiant, ou « EPN : … » pour un répondant.")
    action = models.CharField(max_length=40, db_index=True)
    objet = models.CharField(max_length=255, blank=True)
    detail = models.JSONField(default=dict, blank=True)
    ip = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        ordering = ["-date", "-pk"]
        verbose_name = "entrée du journal d'audit"
        verbose_name_plural = "journal d'audit"

    def __str__(self):
        return f"{self.date:%d/%m/%Y %H:%M} · {self.auteur} · {self.action} · {self.objet}"

    def save(self, *args, **kwargs):
        if self.pk:
            raise PermissionError("Le journal d'audit n'est pas modifiable.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise PermissionError("Le journal d'audit n'est pas modifiable.")


def chemin_logo(instance, nom_fichier):
    import os

    return f"parametres/logo{os.path.splitext(nom_fichier)[1].lower()}"


class Parametres(models.Model):
    """Paramétrage de l'institution (F-48), modifiable depuis l'interface. Une seule ligne."""

    pays = models.CharField(max_length=120, blank=True)
    devise = models.CharField("devise nationale", max_length=200, blank=True)
    ministere = models.CharField("ministère commanditaire", max_length=255, blank=True)
    institution = models.CharField("institution", max_length=255, blank=True)
    monnaie = models.CharField(max_length=40, blank=True, default="", help_text="Ex. « FCFA ». Vide = monnaie locale.")
    logo = models.FileField(upload_to=chemin_logo, blank=True, help_text="PNG ou JPG, 1 Mo maximum.")
    email_contact = models.EmailField("e-mail d'assistance", blank=True)
    texte_invitation = models.TextField(
        "message d'invitation", blank=True, help_text="Paragraphe ajouté en tête des e-mails d'invitation.")
    texte_relance = models.TextField("message de relance", blank=True, help_text="Paragraphe ajouté aux relances.")
    signature = models.TextField("signature des e-mails", blank=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "paramètres"
        verbose_name_plural = "paramètres"

    def __str__(self):
        return "Paramètres de l'application"

    @classmethod
    def charger(cls):
        obj = cls.objects.first()
        return obj or cls()

    def valeur(self, champ):
        """Valeur réglée dans l'interface, à défaut celle du fichier .env."""
        repli = {"pays": "PAYS", "devise": "DEVISE", "ministere": "NOM_MINISTERE", "institution": "NOM_INSTITUTION"}
        return getattr(self, champ) or (getattr(settings, repli[champ], "") if champ in repli else "")


class DoubleAuthentification(models.Model):
    """Double authentification d'un compte de l'équipe (F-03) : application TOTP et codes de secours."""

    utilisateur = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="double_auth")
    secret = models.CharField(max_length=64)
    active = models.BooleanField(default=False)
    dernier_pas = models.BigIntegerField(null=True, blank=True, help_text="Dernier code accepté : refusé s'il est rejoué.")
    codes_secours = models.JSONField(default=list, blank=True, help_text="Empreintes des codes de secours restants.")
    date_activation = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "double authentification"

    def __str__(self):
        return f"{self.utilisateur} · {'active' if self.active else 'en cours'}"

    @staticmethod
    def empreinte(code):
        import hashlib

        return hashlib.sha256(code.strip().upper().replace(" ", "").encode()).hexdigest()

    def verifier(self, code):
        """Code de l'application ou code de secours (consommé). Enregistre le pas accepté."""
        from . import totp

        pas = totp.verifier(self.secret, code, self.dernier_pas)
        if pas is not None:
            self.dernier_pas = pas
            self.save(update_fields=["dernier_pas"])
            return True
        e = self.empreinte(code)
        if self.active and e in self.codes_secours:
            self.codes_secours = [c for c in self.codes_secours if c != e]
            self.save(update_fields=["codes_secours"])
            return True
        return False


def double_auth_active(user):
    da = getattr(user, "double_auth", None)
    return bool(da and da.active)


class SyntheseIA(models.Model):
    """Synthèse rédigée par l'assistant IA pour le rapport annuel : conservée pour ne pas solliciter le modèle à chaque
    téléchargement. Une par campagne, périmètre (tutelles visibles) et base de calcul."""

    campagne = models.ForeignKey(Campagne, on_delete=models.CASCADE, related_name="syntheses_ia")
    perimetre = models.CharField(max_length=1000, blank=True, help_text="Tutelles couvertes, vide = toutes.")
    base = models.CharField(max_length=20, default="validees")
    contenu = models.JSONField(default=dict)
    nombre_reponses = models.PositiveIntegerField(default=0)
    modele = models.CharField(max_length=60, blank=True)
    auteur = models.CharField(max_length=150, blank=True)
    date = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date"]
        constraints = [models.UniqueConstraint(fields=["campagne", "perimetre", "base"], name="synthese_ia_unique")]
        verbose_name = "synthèse IA"
        verbose_name_plural = "synthèses IA"

    def __str__(self):
        return f"{self.campagne} · {self.perimetre or 'tous les EPN'} · {self.base}"
