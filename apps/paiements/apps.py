from django.apps import AppConfig


class PaiementsConfig(AppConfig):
    default_auto_field = "django.db.models.UUIDField"
    name = "apps.paiements"
    verbose_name = "Paiements"

    def ready(self):
        """Importe les signaux pour qu'ils soient enregistrés au démarrage."""
        import apps.paiements.signals  # noqa: F401
