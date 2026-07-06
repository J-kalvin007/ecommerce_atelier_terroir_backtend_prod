from django.apps import AppConfig


class CommandesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.commandes'

    def ready(self):
        import apps.commandes.signals  # noqa
