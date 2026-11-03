from django.urls import path

from . import api

app_name = "api"

urlpatterns = [
    path("csrf/", api.csrf, name="csrf"),
    path("questionnaire/", api.questionnaire, name="questionnaire"),
    path("config/", api.config, name="config"),
    path("formulaire/", api.formulaire_public, name="formulaire_public"),
    # Parcours du répondant
    path("r/<str:jeton>/", api.reponse, name="reponse"),
    path("r/<str:jeton>/identification/", api.identification, name="identification"),
    path("r/<str:jeton>/modules/<str:code>/", api.module, name="module"),
    path("r/<str:jeton>/pieces/<str:code>/", api.piece_publique, name="piece_publique"),
    path("r/<str:jeton>/soumettre/", api.soumettre, name="soumettre"),
    # Équipe d'enquête
    path("auth/moi/", api.moi, name="moi"),
    path("auth/connexion/", api.connexion, name="connexion"),
    path("auth/deconnexion/", api.deconnexion, name="deconnexion"),
    path("gestion/options/", api.options, name="options"),
    path("gestion/tableau-de-bord/", api.tableau_de_bord, name="tableau_de_bord"),
    path("gestion/reponses/", api.reponses, name="reponses"),
    path("gestion/reponses/<int:pk>/", api.reponse_detail, name="reponse_detail"),
    path("gestion/reponses/<int:pk>/pieces.zip", api.pieces_zip, name="pieces_zip"),
    path("gestion/reponses/<int:pk>/<str:action>/", api.reponse_action, name="reponse_action"),
    path("gestion/relancer-retardataires/", api.relancer_retardataires, name="relancer_retardataires"),
    path("gestion/liens/", api.liens, name="liens"),
    path("gestion/liens.xlsx", api.liens_xlsx, name="liens_xlsx"),
    path("gestion/export.xlsx", api.export_xlsx, name="export"),
    path("gestion/statistiques/", api.stats, name="statistiques"),
    path("gestion/pieces/<int:pk>/", api.piece_admin, name="piece_admin"),
    path("gestion/epn/", api.epn_liste, name="epn"),
    path("gestion/campagnes/", api.campagnes, name="campagnes"),
    path("gestion/campagnes/<int:pk>/", api.campagne, name="campagne"),
]
