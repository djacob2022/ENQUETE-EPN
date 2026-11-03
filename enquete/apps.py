from django.apps import AppConfig


class EnqueteConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "enquete"
    verbose_name = "Enquête EPN"

    def ready(self):
        from . import checks, securite, signals  # noqa: F401  (enregistre les contrôles et les récepteurs de signaux)
