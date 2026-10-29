from django.urls import path

from . import views_gestion as v

app_name = "gestion"

urlpatterns = [
    path("", v.tableau_de_bord, name="tableau_de_bord"),
    path("reponses/", v.reponses, name="reponses"),
    path("reponses/<int:pk>/", v.reponse_detail, name="reponse_detail"),
    path("reponses/<int:pk>/rouvrir/", v.reponse_rouvrir, name="reponse_rouvrir"),
    path("reponses/<int:pk>/relancer/", v.relancer, name="relancer"),
    path("reponses/<int:pk>/reinviter/", v.reinviter, name="reinviter"),
    path("relancer-retardataires/", v.relancer_retardataires, name="relancer_retardataires"),
    path("invitations/", v.invitations, name="invitations"),
    path("export.xlsx", v.export, name="export"),
    path("statistiques/", v.stats, name="statistiques"),
    path("epn/", v.epn_liste, name="epn"),
    path("campagnes/", v.campagnes, name="campagnes"),
    path("campagnes/nouvelle/", v.campagne_form, name="campagne_nouvelle"),
    path("campagnes/<int:pk>/", v.campagne_form, name="campagne_modifier"),
    path("questionnaire/", v.questionnaire_apercu, name="questionnaire"),
]
