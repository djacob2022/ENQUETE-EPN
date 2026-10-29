from django.urls import path

from . import views_public as v

app_name = "public"

urlpatterns = [
    path("", v.page_accueil, name="page_accueil"),
    path("r/<str:jeton>/", v.accueil, name="accueil"),
    path("r/<str:jeton>/module/<str:code>/", v.module, name="module"),
    path("r/<str:jeton>/recapitulatif/", v.recapitulatif, name="recapitulatif"),
    path("r/<str:jeton>/merci/", v.merci, name="merci"),
]
