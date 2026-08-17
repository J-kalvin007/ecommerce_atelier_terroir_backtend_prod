from django.apps import AppConfig


class RecettesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.recettes"
    verbose_name = "Recettes de cuisine"

    def ready(self):
        """Importe les signaux pour qu'ils soient enregistrés au démarrage."""
        import apps.recettes.signals  # noqa: F401
