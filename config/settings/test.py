"""
With these settings, tests run faster.
"""

from .base import *  # noqa: F403
from .base import REST_FRAMEWORK
from .base import TEMPLATES
from .base import env

# THROTTLING
# ------------------------------------------------------------------------------
# La limitation de débit est neutralisée pendant les tests : la suite partage
# une même IP/un même client et dépasserait instantanément les quotas anonymes,
# rendant les tests non déterministes (429 aléatoires). Les throttles restent
# évidemment actifs en local/production.
#
# On conserve toutes les CLÉS de scope (les vues chatbot posent des throttle_classes
# explicites qui les recherchent) mais on les mappe à None : DRF interprète un
# taux None comme « aucune limite » et court-circuite allow_request.
REST_FRAMEWORK = {
    **REST_FRAMEWORK,
    "DEFAULT_THROTTLE_CLASSES": [],
    "DEFAULT_THROTTLE_RATES": {
        scope: None for scope in REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]
    },
}

# GENERAL
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#secret-key
SECRET_KEY = env(
    "DJANGO_SECRET_KEY",
    default="riwn9GULVRy40ErbMQHkTmP5fsSC3D2T6D1Q266g6M715sanbcxg6vR5xfpuHDnQ",
)
# https://docs.djangoproject.com/en/dev/ref/settings/#test-runner
TEST_RUNNER = "django.test.runner.DiscoverRunner"

# PASSWORDS
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#password-hashers
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

# EMAIL
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#email-backend
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

# DEBUGGING FOR TEMPLATES
# ------------------------------------------------------------------------------
TEMPLATES[0]["OPTIONS"]["debug"] = True  # type: ignore[index]

# MEDIA
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#media-url
MEDIA_URL = "http://media.testserver/"
# Your stuff...
# ------------------------------------------------------------------------------
