from django.contrib import admin

from .models import EPN, Campagne, Envoi, Reponse


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
