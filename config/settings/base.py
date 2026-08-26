# ruff: noqa: ERA001, E501
"""Base settings to build other settings files upon."""

import ssl
from pathlib import Path
import environ
from celery.schedules import crontab
import paydunya


BASE_DIR = Path(__file__).resolve(strict=True).parent.parent.parent
# ecommerce_backend/
APPS_DIR = BASE_DIR / "ecommerce_backend"
env = environ.Env()

READ_DOT_ENV_FILE = env.bool("DJANGO_READ_DOT_ENV_FILE", default=False)
if READ_DOT_ENV_FILE:
    # OS environment variables take precedence over variables from .env
    env.read_env(str(BASE_DIR / ".env"))



ALLOWED_HOSTS =[
    "*",
    "https://atelierterroirsolime-gyiybtd2n-j-kalvins-projects.vercel.app",
]

CORS_URLS_REGEX = r"^/api/.*$"

# CORS
CORS_ALLOW_ALL_ORIGINS = True

from corsheaders.defaults import default_headers
CORS_ALLOW_HEADERS = list(default_headers) + [
    "ngrok-skip-browser-warning",
]

# Disable CORS_ALLOW_CREDENTIALS to allow wildcard origin
# CORS_ALLOW_CREDENTIALS = False

CORS_ALLOWED_ORIGINS = [
    "https://atelierterroirsolime-gyiybtd2n-j-kalvins-projects.vercel.app",
]

# CORS_ALLOW_CREDENTIALS = True


# GENERAL
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#debug
DEBUG = env.bool("DJANGO_DEBUG", False)
# Local time zone. Choices are
# http://en.wikipedia.org/wiki/List_of_tz_zones_by_name
# though not all of them may be available with every OS.
# In Windows, this must be set to your system time zone.
TIME_ZONE = "UTC"
# https://docs.djangoproject.com/en/dev/ref/settings/#language-code
LANGUAGE_CODE = "en-us"
# https://docs.djangoproject.com/en/dev/ref/settings/#languages
# from django.utils.translation import gettext_lazy as _
# LANGUAGES = [
#     ('en', _('English')),
#     ('fr-fr', _('French')),
#     ('pt-br', _('Portuguese')),
# ]
# https://docs.djangoproject.com/en/dev/ref/settings/#site-id
SITE_ID = 1
# https://docs.djangoproject.com/en/dev/ref/settings/#use-i18n
USE_I18N = True
# https://docs.djangoproject.com/en/dev/ref/settings/#use-tz
USE_TZ = True
# https://docs.djangoproject.com/en/dev/ref/settings/#locale-paths
LOCALE_PATHS = [str(BASE_DIR / "locale")]

# DATABASES
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#databases
DATABASES = {"default": env.db("DATABASE_URL")}
DATABASES["default"]["ATOMIC_REQUESTS"] = True
# https://docs.djangoproject.com/en/stable/ref/settings/#std:setting-DEFAULT_AUTO_FIELD
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# URLS
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#root-urlconf
ROOT_URLCONF = "config.urls"
# https://docs.djangoproject.com/en/dev/ref/settings/#wsgi-application
WSGI_APPLICATION = "config.wsgi.application"

# APPS
# ------------------------------------------------------------------------------
DJANGO_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.sites",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # "django.contrib.humanize", # Handy template tags
    "django.contrib.admin",
    "django.forms",
]

THIRD_PARTY_APPS = [
    "crispy_forms",
    "crispy_bootstrap5",
    "allauth",
    "allauth.account",
    "allauth.mfa",
    "allauth.socialaccount",
    "django_celery_beat",
    "rest_framework",
    "rest_framework.authtoken",
    "dj_rest_auth",
    "corsheaders",
    "drf_spectacular",
    "dj_rest_auth.registration",
]

LOCAL_APPS = [
    "ecommerce_backend.users",
    "apps.catalog",
    "apps.core",
    "apps.commandes",
    "apps.paiements",
    "apps.promotions",
    "apps.fidelites",
    "apps.livraisons",
    "apps.notifications",
    "apps.recettes",
    # ── Chatbot IA ─────────────────────────────────────────────────────────────
    "apps.chatbot",

    # Your stuff: custom apps go here
]
# https://docs.djangoproject.com/en/dev/ref/settings/#installed-apps
INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

# MIGRATIONS
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#migration-modules
MIGRATION_MODULES = {"sites": "ecommerce_backend.contrib.sites.migrations"}

# AUTHENTICATION
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#authentication-backends
AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]
# https://docs.djangoproject.com/en/dev/ref/settings/#auth-user-model
AUTH_USER_MODEL = "users.User"
# https://docs.djangoproject.com/en/dev/ref/settings/#login-redirect-url
LOGIN_REDIRECT_URL = "users:redirect"
# https://docs.djangoproject.com/en/dev/ref/settings/#login-url
LOGIN_URL = "account_login"

# PASSWORDS
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#password-hashers
PASSWORD_HASHERS = [
    # https://docs.djangoproject.com/en/dev/topics/auth/passwords/#using-argon2-with-django
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
    "django.contrib.auth.hashers.BCryptSHA256PasswordHasher",
]
# https://docs.djangoproject.com/en/dev/ref/settings/#auth-password-validators
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# MIDDLEWARE
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#middleware
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "allauth.account.middleware.AccountMiddleware",
]

# STATIC
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#static-root
STATIC_ROOT = str(BASE_DIR / "staticfiles")
# https://docs.djangoproject.com/en/dev/ref/settings/#static-url
STATIC_URL = "/static/"
# https://docs.djangoproject.com/en/dev/ref/contrib/staticfiles/#std:setting-STATICFILES_DIRS
STATICFILES_DIRS = [str(APPS_DIR / "static")]
# https://docs.djangoproject.com/en/dev/ref/contrib/staticfiles/#staticfiles-finders
STATICFILES_FINDERS = [
    "django.contrib.staticfiles.finders.FileSystemFinder",
    "django.contrib.staticfiles.finders.AppDirectoriesFinder",
]

# MEDIA
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#media-root
MEDIA_ROOT = str(APPS_DIR / "media")
# https://docs.djangoproject.com/en/dev/ref/settings/#media-url
MEDIA_URL = "/media/"

# TEMPLATES
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#templates
TEMPLATES = [
    {
        # https://docs.djangoproject.com/en/dev/ref/settings/#std:setting-TEMPLATES-BACKEND
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        # https://docs.djangoproject.com/en/dev/ref/settings/#dirs
        "DIRS": [str(APPS_DIR / "templates")],
        # https://docs.djangoproject.com/en/dev/ref/settings/#app-dirs
        "APP_DIRS": True,
        "OPTIONS": {
            # https://docs.djangoproject.com/en/dev/ref/settings/#template-context-processors
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.template.context_processors.i18n",
                "django.template.context_processors.media",
                "django.template.context_processors.static",
                "django.template.context_processors.tz",
                "django.contrib.messages.context_processors.messages",
                "ecommerce_backend.users.context_processors.allauth_settings",
            ],
        },
    },
]

# https://docs.djangoproject.com/en/dev/ref/settings/#form-renderer
FORM_RENDERER = "django.forms.renderers.TemplatesSetting"

# http://django-crispy-forms.readthedocs.io/en/latest/install.html#template-packs
CRISPY_TEMPLATE_PACK = "bootstrap5"
CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"

# FIXTURES
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#fixture-dirs
FIXTURE_DIRS = (str(APPS_DIR / "fixtures"),)

# SECURITY
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#session-cookie-httponly
SESSION_COOKIE_HTTPONLY = True
# https://docs.djangoproject.com/en/dev/ref/settings/#csrf-cookie-httponly
CSRF_COOKIE_HTTPONLY = True
# https://docs.djangoproject.com/en/dev/ref/settings/#x-frame-options
X_FRAME_OPTIONS = "DENY"

# EMAIL
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#email-backend
# EMAIL_BACKEND = env(
#     "DJANGO_EMAIL_BACKEND",
#     default="django.core.mail.backends.smtp.EmailBackend",
# )
EMAIL_BACKEND = env("DJANGO_EMAIL_BACKEND", default="django.core.mail.backends.smtp.EmailBackend")

# https://docs.djangoproject.com/en/dev/ref/settings/#email-timeout
EMAIL_TIMEOUT = 5

DEFAULT_FROM_EMAIL = env("DJANGO_DEFAULT_FROM_EMAIL", default="atelierduterroir@solime.com") 

# ADMIN
# ------------------------------------------------------------------------------
# Django Admin URL.
ADMIN_URL = "admin/"
# https://docs.djangoproject.com/en/dev/ref/settings/#admins
ADMINS = [("""Takoudjou Kalvin Moise""", "takoudjoumoisecalvin@gmail.com")]
# https://docs.djangoproject.com/en/dev/ref/settings/#managers
MANAGERS = ADMINS

# URL du Frontend (Next.js) pour les redirections (emails, paiements, etc.)
FRONTEND_URL = env("FRONTEND_URL", default="https://atelierterroirsolime.vercel.app")
BACKEND_URL = env("BACKEND_URL", default="https://ecommerce-atelier-terroir-backtend-prod.onrender.com")
# https://cookiecutter-django.readthedocs.io/en/latest/settings.html#other-environment-settings
# Force the `admin` sign in process to go through the `django-allauth` workflow
DJANGO_ADMIN_FORCE_ALLAUTH = env.bool("DJANGO_ADMIN_FORCE_ALLAUTH", default=False)

# LOGGING
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#logging
# See https://docs.djangoproject.com/en/dev/topics/logging for
# more details on how to customize your logging configuration.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "%(levelname)s %(asctime)s %(module)s %(process)d %(thread)d %(message)s",
        },
    },
    "handlers": {
        "console": {
            "level": "DEBUG",
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "root": {"level": "INFO", "handlers": ["console"]},
}

REDIS_URL = env("REDIS_URL", default="redis://redis:6379/0")
REDIS_SSL = REDIS_URL.startswith("rediss://")

# Celery
# ------------------------------------------------------------------------------
if USE_TZ:
    # https://docs.celeryq.dev/en/stable/userguide/configuration.html#std:setting-timezone
    CELERY_TIMEZONE = TIME_ZONE
# https://docs.celeryq.dev/en/stable/userguide/configuration.html#std:setting-broker_url
CELERY_BROKER_URL = REDIS_URL
# https://docs.celeryq.dev/en/stable/userguide/configuration.html#redis-backend-use-ssl
CELERY_BROKER_USE_SSL = {"ssl_cert_reqs": ssl.CERT_NONE} if REDIS_SSL else None
# https://docs.celeryq.dev/en/stable/userguide/configuration.html#std:setting-result_backend
CELERY_RESULT_BACKEND = REDIS_URL
# https://docs.celeryq.dev/en/stable/userguide/configuration.html#redis-backend-use-ssl
CELERY_REDIS_BACKEND_USE_SSL = CELERY_BROKER_USE_SSL
# https://docs.celeryq.dev/en/stable/userguide/configuration.html#result-extended
CELERY_RESULT_EXTENDED = True
# https://docs.celeryq.dev/en/stable/userguide/configuration.html#result-backend-always-retry
# https://github.com/celery/celery/pull/6122
CELERY_RESULT_BACKEND_ALWAYS_RETRY = True
# https://docs.celeryq.dev/en/stable/userguide/configuration.html#result-backend-max-retries
CELERY_RESULT_BACKEND_MAX_RETRIES = 10
# https://docs.celeryq.dev/en/stable/userguide/configuration.html#std:setting-accept_content
CELERY_ACCEPT_CONTENT = ["json"]
# https://docs.celeryq.dev/en/stable/userguide/configuration.html#std:setting-task_serializer
CELERY_TASK_SERIALIZER = "json"
# https://docs.celeryq.dev/en/stable/userguide/configuration.html#std:setting-result_serializer
CELERY_RESULT_SERIALIZER = "json"
# https://docs.celeryq.dev/en/stable/userguide/configuration.html#task-time-limit
# TODO: set to whatever value is adequate in your circumstances
CELERY_TASK_TIME_LIMIT = 5 * 60
# https://docs.celeryq.dev/en/stable/userguide/configuration.html#task-soft-time-limit
# TODO: set to whatever value is adequate in your circumstances
CELERY_TASK_SOFT_TIME_LIMIT = 60
# https://docs.celeryq.dev/en/stable/userguide/configuration.html#beat-scheduler
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"
# https://docs.celeryq.dev/en/stable/userguide/configuration.html#worker-send-task-events
CELERY_WORKER_SEND_TASK_EVENTS = True
# https://docs.celeryq.dev/en/stable/userguide/configuration.html#std-setting-task_send_sent_event
CELERY_TASK_SEND_SENT_EVENT = True
# https://docs.celeryq.dev/en/stable/userguide/configuration.html#worker-hijack-root-logger
CELERY_WORKER_HIJACK_ROOT_LOGGER = False
# django-allauth
# ------------------------------------------------------------------------------

ACCOUNT_EMAIL_REQUIRED = True

ACCOUNT_ALLOW_REGISTRATION = env.bool("DJANGO_ACCOUNT_ALLOW_REGISTRATION", True)
# https://docs.allauth.org/en/latest/account/configuration.html
ACCOUNT_LOGIN_METHODS = {"email"}
# https://docs.allauth.org/en/latest/account/configuration.html
ACCOUNT_SIGNUP_FIELDS = ["email*", "password1*", "password2*"]
# https://docs.allauth.org/en/latest/account/configuration.html
ACCOUNT_USER_MODEL_USERNAME_FIELD = None
# https://docs.allauth.org/en/latest/account/configuration.html
ACCOUNT_EMAIL_VERIFICATION = "mandatory"
# https://docs.allauth.org/en/latest/account/configuration.html
ACCOUNT_ADAPTER = "ecommerce_backend.users.adapters.AccountAdapter"
# https://docs.allauth.org/en/latest/account/forms.html
ACCOUNT_FORMS = {"signup": "ecommerce_backend.users.forms.UserSignupForm"}
# https://docs.allauth.org/en/latest/socialaccount/configuration.html
SOCIALACCOUNT_ADAPTER = "ecommerce_backend.users.adapters.SocialAccountAdapter"
# https://docs.allauth.org/en/latest/socialaccount/configuration.html
SOCIALACCOUNT_FORMS = {"signup": "ecommerce_backend.users.forms.UserSocialSignupForm"}

# django-rest-framework
# -------------------------------------------------------------------------------
# django-rest-framework - https://www.django-rest-framework.org/api-guide/settings/
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework.authentication.SessionAuthentication",
        "rest_framework.authentication.TokenAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    # ─── Limitation de débit ──────────────────────────────────────────────────
    # Filet global appliqué à TOUTES les vues DRF. Les valeurs sont volontairement
    # larges : elles n'entravent pas une navigation normale mais coupent court
    # au scraping et au bourrinage d'endpoints.
    # Les vues coûteuses (IA / OpenAI) surchargent ces classes avec des scopes
    # dédiés et beaucoup plus bas — voir apps/chatbot/throttles.py.
    "DEFAULT_THROTTLE_CLASSES": (
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ),
    "DEFAULT_THROTTLE_RATES": {
        # Portée globale
        "anon": env("THROTTLE_RATE_ANON", default="60/min"),
        "user": env("THROTTLE_RATE_USER", default="240/min"),
        # Chatbot IA — chaque requête déclenche jusqu'à 2 appels OpenAI (1000 tokens)
        "chatbot_anon": env("THROTTLE_RATE_CHATBOT_ANON", default="10/hour"),
        "chatbot_user": env("THROTTLE_RATE_CHATBOT_USER", default="60/hour"),
        "chatbot_monthly": env("THROTTLE_RATE_CHATBOT_MONTHLY", default="500/month"),
        # Recherche IA — 1 appel OpenAI (jusqu'à 1500 tokens)
        "ai_search_anon": env("THROTTLE_RATE_AI_SEARCH_ANON", default="10/hour"),
        "ai_search_user": env("THROTTLE_RATE_AI_SEARCH_USER", default="60/hour"),
        "ai_search_monthly": env("THROTTLE_RATE_AI_SEARCH_MONTHLY", default="500/month"),
        # Recommandations — 100 % ORM, pas d'appel externe : quotas plus souples
        "recommendation_anon": env("THROTTLE_RATE_RECO_ANON", default="60/hour"),
        "recommendation_user": env("THROTTLE_RATE_RECO_USER", default="300/hour"),
    },
}


REST_AUTH_REGISTER_SERIALIZERS = {
    "REGISTER_SERIALIZER": "ecommerce_backend.users.serializers.CustomRegisterSerializer",
}


REST_AUTH = {
    "USE_JWT": False,
    "PASSWORD_RESET_URL_GENERATOR": "ecommerce_backend.users.utils.password_reset_url_generator",
    "PASSWORD_RESET_SERIALIZER": "ecommerce_backend.users.serializers.CustomPasswordResetSerializer",
}


REST_USE_JWT = False



# django-cors-headers - https://github.com/adamchainz/django-cors-headers#setup
CORS_URLS_REGEX = r"^/api/.*$"

# By Default swagger ui is available only to admin user(s). You can change permission classes to change that
# See more configuration options at https://drf-spectacular.readthedocs.io/en/latest/settings.html#settings
SPECTACULAR_SETTINGS = {
    "TITLE": "ecommerce_backend API",
    "DESCRIPTION": "Documentation of API endpoints of ecommerce_backend",
    "VERSION": "1.0.0",
    "SERVE_PERMISSIONS": ["rest_framework.permissions.AllowAny"],
    "SCHEMA_PATH_PREFIX": "/api/",
}
# Your stuff...
# ------------------------------------------------------------------------------








# Durée de validité des points en jours (365 = 1 an)
LOYALTY_POINTS_EXPIRY_DAYS = env.int("LOYALTY_POINTS_EXPIRY_DAYS", 365)

# Bonus de points
LOYALTY_REFERRAL_BONUS_POINTS = env.int("LOYALTY_REFERRAL_BONUS_POINTS", 200)
LOYALTY_BIRTHDAY_BONUS_POINTS = env.int("LOYALTY_BIRTHDAY_BONUS_POINTS", 500)
LOYALTY_FIRST_PURCHASE_BONUS_POINTS = env.int("LOYALTY_FIRST_PURCHASE_BONUS_POINTS", 100)

# ─── Celery Beat Schedule ────────────────────────────────────────────────
# Ajouter dans CELERY_BEAT_SCHEDULE (si vous utilisez django-celery-beat)


# ATTENTION — Cette planification n'est exploitée que si un service `celery beat`
# ET un service `celery worker` distincts sont réellement déployés. En production
# (config/settings/production.py) Celery tourne en mode EAGER avec un broker
# `memory://` : le planificateur n'existe pas et AUCUNE tâche listée ici ne
# s'exécute jamais. Le chemin fiable aujourd'hui est la commande de management
# `expirer_points_fidelite`, à brancher sur un cron Render :
#     python manage.py expirer_points_fidelite
#
# Les clés `task` doivent correspondre au NOM ENREGISTRÉ de la tâche
# (`@shared_task(name=...)`), pas à son chemin d'import : l'ancienne valeur
# "apps.fidelites.tasks.expire_points_task" n'était résolue par aucun worker.
# L'entrée "birthday-bonus-daily" a été retirée : `birthday_bonus_task` n'existe
# pas dans le code et le modèle User ne porte aucune date de naissance ; la
# planifier revenait à programmer un échec quotidien silencieux.
CELERY_BEAT_SCHEDULE = {
    "expire-loyalty-points-daily": {
        "task": "loyalty.expire_points",
        "schedule": crontab(hour=2, minute=0),  # Tous les jours à 02:00 UTC
    },
}


# Supprimer les anciennes clés pour éviter les warnings
ACCOUNT_EMAIL_REQUIRED = True  # déjà implicite, mais peut être laissé
# Les deux lignes suivantes sont celles qui manquent :
OLD_ACCOUNT_EMAIL_REQUIRED = False  # Indique qu'on utilise la nouvelle config
OLD_ACCOUNT_USERNAME_REQUIRED = False

ACCOUNT_USERNAME_REQUIRED = False





# ─── PayDunya ─────────────────────────────────────────────────────────────────

# PAYDUNYA CONFIG
# SÉCURITÉ — Aucune valeur de repli secrète n'est codée dans le dépôt.
# Les quatre clés proviennent EXCLUSIVEMENT de l'environnement :
#   - local  : .envs/.local/.payDunya (chargé par config/settings/local.py)
#   - prod   : variables d'environnement Render
# En l'absence de variable, la valeur est vide : la passerelle refuse alors de
# fonctionner (voir PayDunyaGateway) et config/settings/production.py fait
# échouer le démarrage explicitement.
PAYDUNYA_CONFIG = {
    "MASTER_KEY": env("PAYDUNYA_MASTER_KEY", default=""),
    "PUBLIC_KEY": env("PAYDUNYA_PUBLIC_KEY", default=""),
    "PRIVATE_KEY": env("PAYDUNYA_PRIVATE_KEY", default=""),
    "TOKEN": env("PAYDUNYA_TOKEN", default=""),
    "MODE": env("PAYDUNYA_MODE", default="test"),
}

# Exposition à plat des clés, attendue par apps.paiements.gateways.paydunya.PayDunyaGateway.
# Sans ces settings, la passerelle démarrait avec des clés vides et tout appel
# serveur→PayDunya (notamment verify_payment) était rejeté en 401.
PAYDUNYA_MASTER_KEY = PAYDUNYA_CONFIG["MASTER_KEY"]
PAYDUNYA_PUBLIC_KEY = PAYDUNYA_CONFIG["PUBLIC_KEY"]
PAYDUNYA_PRIVATE_KEY = PAYDUNYA_CONFIG["PRIVATE_KEY"]
PAYDUNYA_TOKEN = PAYDUNYA_CONFIG["TOKEN"]
PAYDUNYA_MODE = PAYDUNYA_CONFIG["MODE"]
# En mode test → URL sandbox PayDunya. En mode live → URL production.
# La gateway custom (PayDunyaGateway) fait ses appels HTTP directement,
# elle doit donc cibler la bonne URL selon le mode — contrairement à
# la lib paydunya qui gère ça automatiquement via paydunya.debug.
_paydunya_default_base = (
    "https://app.paydunya.com/sandbox-api/v1"
    if PAYDUNYA_MODE == "test"
    else "https://app.paydunya.com/api/v1"
)
PAYDUNYA_BASE_URL = env("PAYDUNYA_BASE_URL", default=_paydunya_default_base)

PAYDUNYA_URLS = {
    "test": "https://paydunya.com",
    "live": "https://paydunya.com",
}

# 🔄 Remplacement des chaînes en dur par la variable dynamique FRONTEND_URL
PAYDUNYA_CANCEL_URL = f"{FRONTEND_URL}/paiement/commande/echec"
PAYDUNYA_RETURN_URL = f"{FRONTEND_URL}/paiement/commande/success"

PAYDUNYA_WALLET_CANCEL_URL = f"{FRONTEND_URL}/paiement/wallet/echec"
PAYDUNYA_WALLET_SUCCESS_URL = f"{FRONTEND_URL}/paiement/wallet/success"

paydunya.api_keys = {
    "PAYDUNYA-MASTER-KEY": PAYDUNYA_CONFIG["MASTER_KEY"],
    "PAYDUNYA-PRIVATE-KEY": PAYDUNYA_CONFIG["PRIVATE_KEY"],
    "PAYDUNYA-TOKEN": PAYDUNYA_CONFIG["TOKEN"],
}

# On peut utiliser MODE test ou live en fonction de l'environnement, ici debug est True par défaut comme initialement
paydunya.debug = True

PAYDUNYA_CALLBACK_URL = f"{BACKEND_URL}/api/v1/paiements/ipn/"


# ─── OpenAI / Chatbot IA ──────────────────────────────────────────────────────
# Clé API OpenAI — À définir dans la variable d'environnement OPENAI_API_KEY
# Ne jamais mettre la clé en dur dans le code source.
OPENAI_API_KEY = env("OPENAI_API_KEY", default="")
OPENAI_API_BASE = env("OPENAI_API_BASE", default="https://api.openai.com/v1")

# Modèle OpenAI à utiliser pour le chatbot.
# openai/gpt-4o-mini est le rapport qualité/coût optimal pour un chatbot e-commerce.
# Peut être remplacé par "gpt-4o" pour des réponses plus riches.
OPENAI_MODEL = env("OPENAI_MODEL", default="openai/gpt-4o-mini")