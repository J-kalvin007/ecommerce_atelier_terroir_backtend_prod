from django.apps import AppConfig


class PromotionsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.promotions"
    verbose_name = "Promotions"

    def ready(self):
        """Importe les signaux au démarrage."""
        import apps.promotions.signals  # noqa: F401