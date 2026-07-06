
from django.apps import AppConfig


class LoyaltyConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.fidelites"
    verbose_name = "Fidélité"

    def ready(self):
        """Importe les signaux au démarrage."""
        import apps.fidelites.signals  # noqa: F401