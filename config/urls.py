from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("api/", include("enquete.urls_api")),
    path("django-admin/", admin.site.urls),
    path("", include("enquete.urls_public")),
]
