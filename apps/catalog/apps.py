from django.apps import AppConfig


class CatalogConfig(AppConfig):
    name = 'apps.catalog'


    def ready(self):
        """Importe les signaux pour qu'ils soient enregistrés au démarrage."""
        import apps.catalog.signals  # noqa: F401