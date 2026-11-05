from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin

from .models import EPN, Campagne, Envoi, Journal, ListeReference, Parametres, PieceJointe, ProfilEquipe, Reponse


@admin.register(EPN)
class EPNAdmin(admin.ModelAdmin):
    list_display = ["nom", "sigle", "categorie", "tutelle", "region", "email_contact", "etat"]
    list_filter = ["categorie", "tutelle", "etat"]
    exclude = ["actif"]
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
    verbose_name_plural = "Rôle et périmètre dans l'espace de gestion"


class UtilisateurAdmin(UserAdmin):
    inlines = [ProfilEquipeEnLigne]


admin.site.unregister(get_user_model())
admin.site.register(get_user_model(), UtilisateurAdmin)


@admin.register(ListeReference)
class ListeReferenceAdmin(admin.ModelAdmin):
    list_display = ["libelle", "type"]
    list_filter = ["type"]


@admin.register(Parametres)
class ParametresAdmin(admin.ModelAdmin):
    list_display = ["__str__", "institution", "date_modification"]


@admin.register(Journal)
class JournalAdmin(admin.ModelAdmin):
    """Consultation seule : le journal d'audit n'est ni modifiable ni supprimable."""

    list_display = ["date", "auteur", "action", "objet", "ip"]
    list_filter = ["action"]
    search_fields = ["auteur", "objet"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
