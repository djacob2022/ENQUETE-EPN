"""Pages de l'interface React. Les noms servent à construire les liens envoyés par e-mail."""
from django.urls import path, re_path

from .spa import application

app_name = "public"

urlpatterns = [
    path("", application, name="page_accueil"),
    path("r/<str:jeton>/", application, name="accueil"),
    re_path(r"^(?:r|gestion|connexion|formulaire)(?:/.*)?$", application, name="application"),
]
