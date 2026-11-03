from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin

from .models import EPN, Campagne, Envoi, PieceJointe, ProfilEquipe, Reponse


@admin.register(EPN)
class EPNAdmin(admin.ModelAdmin):
    list_display = ["nom", "sigle", "categorie", "tutelle", "region", "email_contact", "actif"]
    list_filter = ["categorie", "tutelle", "actif"]
    search_fields = ["nom", "sigle", "email_contact"]


@admin.register(Campagne)
class CampagneAdmin(admin.ModelAdmin):
    list_display = ["nom", "exercice", "date_ouverture", "date_cloture", "active"]


@admin.register(Reponse)
class ReponseAdmin(admin.ModelAdmin):
    list_display = ["epn", "campagne", "statut", "nom", "prenom", "date_soumission"]
    list_filter = ["campagne", "statut"]
    search_fields = ["epn__nom", "nom", "prenom", "email"]
    readonly_fields = ["jeton"]


@admin.register(Envoi)
class EnvoiAdmin(admin.ModelAdmin):
    list_display = ["reponse", "type", "destinataires", "date", "succes", "par"]
    list_filter = ["type", "succes"]


@admin.register(PieceJointe)
class PieceJointeAdmin(admin.ModelAdmin):
    list_display = ["reponse", "code", "nom_original", "taille", "date_depot"]
    list_filter = ["code"]
    search_fields = ["reponse__epn__nom", "nom_original"]


class ProfilEquipeEnLigne(admin.StackedInline):
    model = ProfilEquipe
    can_delete = False
    verbose_name_plural = "Périmètre dans l'espace administrateur"


class UtilisateurAdmin(UserAdmin):
    inlines = [ProfilEquipeEnLigne]


admin.site.unregister(get_user_model())
admin.site.register(get_user_model(), UtilisateurAdmin)
