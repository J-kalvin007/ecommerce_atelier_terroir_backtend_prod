from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class UsersConfig(AppConfig):
    name = "ecommerce_backend.users"
    verbose_name = _("Users")

    def ready(self):
        import ecommerce_backend.users.signals