import secrets

from django.db import models
from django.utils import timezone


def nouveau_jeton():
    return secrets.token_urlsafe(24)


class EPN(models.Model):
    class Categorie(models.TextChoices):
        EPA = "EPA", "EPA"
        EPIC = "EPIC", "EPIC"
        AUTRE = "AUTRE", "Autre"

    nom = models.CharField("dénomination", max_length=255, unique=True)
    sigle = models.CharField(max_length=50, blank=True)
    categorie = models.CharField("catégorie", max_length=10, choices=Categorie.choices, default=Categorie.EPA)
    tutelle = models.CharField("tutelle technique", max_length=255)
    region = models.CharField("région", max_length=120, blank=True)
    email_contact = models.EmailField("e-mail du point focal")
    actif = models.BooleanField(default=True)

    class Meta:
        ordering = ["nom"]
        verbose_name = "EPN"
        verbose_name_plural = "EPN"

    def __str__(self):
        return f"{self.nom} ({self.sigle})" if self.sigle else self.nom


class Campagne(models.Model):
    nom = models.CharField(max_length=200)
    exercice = models.PositiveIntegerField("exercice de référence")
    date_ouverture = models.DateField()
    date_cloture = models.DateField("date de clôture")
    active = models.BooleanField(
        default=True, help_text="Une seule campagne active : celle que voient les liens envoyés aux EPN."
    )

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
    def est_ouverte(self):
        aujourd_hui = timezone.localdate()
        return self.date_ouverture <= aujourd_hui <= self.date_cloture


class Reponse(models.Model):
    """La réponse d'un EPN à une campagne. Créée à l'envoi de l'invitation, avec un lien personnel."""

    class Statut(models.TextChoices):
        INVITE = "invite", "Invité, non commencé"
        EN_COURS = "en_cours", "En cours de saisie"
        SOUMIS = "soumis", "Soumis"

    campagne = models.ForeignKey(Campagne, on_delete=models.CASCADE, related_name="reponses")
    epn = models.ForeignKey(EPN, on_delete=models.CASCADE, related_name="reponses")
    jeton = models.CharField(max_length=64, unique=True, default=nouveau_jeton, editable=False)
    statut = models.CharField(max_length=10, choices=Statut.choices, default=Statut.INVITE)

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
        return self.statut == self.Statut.SOUMIS

    @property
    def repondant(self):
        return f"{self.prenom} {self.nom}".strip()

    def avancement(self):
        from .questionnaire import MODULES

        return round(100 * len(self.modules_completes) / len(MODULES))


class Envoi(models.Model):
    """Journal des e-mails envoyés (invitations et relances)."""

    class Type(models.TextChoices):
        INVITATION = "invitation", "Invitation"
        RELANCE = "relance", "Relance"
        ACCUSE = "accuse", "Accusé de réception"

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
