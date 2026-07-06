from django.apps import AppConfig

class LivraisonsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.livraisons'
    verbose_name = 'Livraisons'

    def ready(self):
        """Importe les signaux pour qu'ils soient enregistrés au démarrage."""
        import apps.livraisons.signals  # noqa: F401
