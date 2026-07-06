import os
import  paydunya
from .base import *  # noqa: F403
from .base import INSTALLED_APPS
from .base import MIDDLEWARE
from .base import env

# ─── Lecture des fichiers .envs/.local/ ───────────────────────────────────────
# Charge automatiquement les variables d'environnement depuis les trois fichiers
# dédiés de l'environnement de développement local.
# Cela évite d'avoir un .env à la racine ; chaque domaine (django, postgres,
# paiement) a son propre fichier versionnable (sauf données sensibles).
# ------------------------------------------------------------------------------
import pathlib as _pathlib

_ENVS_LOCAL = _pathlib.Path(__file__).resolve().parent.parent.parent / ".envs" / ".local"
for _env_file in (".django", ".postgres", ".payDunya"):
    _env_path = _ENVS_LOCAL / _env_file
    if _env_path.exists():
        env.read_env(str(_env_path), overwrite=False)

# GENERAL
# ------------------------------------------------------------------------------
DEBUG = True
SECRET_KEY = env(
    "DJANGO_SECRET_KEY",
    default="Skd9VFlOLU7J8EiarvbHrzqRkc0MS5vuVIGYaXcYgJNh2lyQDP1MVmnWT2BAS2Iv",
)
ALLOWED_HOSTS = [

    "*",
    ".ngrok-free.dev",
]

CSRF_TRUSTED_ORIGINS = [

    "https://*.ngrok-free.dev",
]

# FRONTEND_URL = env("FRONTEND_URL", default="http://localhost:3000")

# BACKEND_URL = env("BACKEND_URL", default="https://outrage-dealer-entrap.ngrok-free.dev")


# CACHES - LocMemCache, pas Redis (Redis n'est plus dans la stack locale)
# ------------------------------------------------------------------------------
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "",
    },
}

# DATABASE - Connexion non-persistante en local pour éviter "too many clients"
# En production, utiliser PgBouncer plutôt que CONN_MAX_AGE élevé.
# ------------------------------------------------------------------------------
DATABASES["default"]["CONN_MAX_AGE"] = 0  # noqa: F405

# EMAIL
# ------------------------------------------------------------------------------

EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
# EMAIL_HOST = env("EMAIL_HOST", default="mailpit")
EMAIL_HOST = "mailpit" 
EMAIL_PORT = 1025

EMAIL_USE_TLS = False
EMAIL_USE_SSL = False

# CELERY - Mode synchrone : pas besoin de Redis ni de Workers
# ------------------------------------------------------------------------------
# Les tâches Celery sont exécutées directement dans le process Django.
# Économie : ~1 GB RAM (plus de celeryworker, celerybeat) + Redis supprimé.
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
# On pointe quand même sur Redis pour ne pas crasher si une tâche est dispatched
# mais il n'est pas nécessaire de faire tourner le container redis
CELERY_BROKER_URL = env("REDIS_URL", default="memory://")
CELERY_RESULT_BACKEND = env("REDIS_URL", default="cache+memory://")

# STATIC FILES - Whitenoise désactivé en local (le serveur de dev Django suffit)
# ------------------------------------------------------------------------------
# Whitenoise en développement ajoute de la latence inutile.
# Le serveur de dev Django sert les fichiers statiques nativement.
INSTALLED_APPS = ["whitenoise.runserver_nostatic", *INSTALLED_APPS]

# DEBUG TOOLBAR - Conditionnel pour ne pas systématiquement alourdir l'API
# ------------------------------------------------------------------------------
# Activez uniquement quand vous déboguez des vues HTML (pas l'API REST).
# Commande : ENABLE_DEBUG_TOOLBAR=true docker compose up
ENABLE_DEBUG_TOOLBAR = env.bool("ENABLE_DEBUG_TOOLBAR", default=False)
if ENABLE_DEBUG_TOOLBAR:
    INSTALLED_APPS += ["debug_toolbar"]
    MIDDLEWARE += ["debug_toolbar.middleware.DebugToolbarMiddleware"]
    DEBUG_TOOLBAR_CONFIG = {
        "DISABLE_PANELS": [
            "debug_toolbar.panels.redirects.RedirectsPanel",
            "debug_toolbar.panels.profiling.ProfilingPanel",
        ],
        "SHOW_TEMPLATE_CONTEXT": True,
    }
    INTERNAL_IPS = ["127.0.0.1", "10.0.2.2"]
    if env("USE_DOCKER", default="no") == "yes":
        import socket
        hostname, _, ips = socket.gethostbyname_ex(socket.gethostname())
        INTERNAL_IPS += ["".join([*ip.split(".")[:-1], ".1"]) for ip in ips]

# RELOADER - Désactiver RunServerPlus polling (cause CPU à 100% sur Windows/Docker)
# ------------------------------------------------------------------------------
# On N'utilise PAS RunServerPlus stat poller : il scanne des milliers de fichiers
# chaque seconde (dont tout le .venv) à travers le bridge WSL2/Windows → CPU 100%
# Django native reloader (watchfiles) est plus efficace avec le volume Docker.
if env("USE_DOCKER", default="no") == "yes":
    # Utilise watchfiles (natif Django 4.2+) plutôt que le poller stat
    # watchfiles détecte les changements via événements filesystem (inotify)
    # au lieu de scanner tous les fichiers en boucle.
    pass  # Ne pas définir RUNSERVERPLUS_POLLER_RELOADER_TYPE

# DJANGO-EXTENSIONS
# ------------------------------------------------------------------------------
INSTALLED_APPS += ["django_extensions"]

# Celery beat propagation
# ------------------------------------------------------------------------------
CELERY_TASK_EAGER_PROPAGATES = True


# ─── PayDunya ─────────────────────────────────────────────────────────────────

# PAYDUNYA CONFIG

PAYDUNYA_CONFIG = {
    "MASTER_KEY": env("PAYDUNYA_MASTER_KEY", default=""),
    "PUBLIC_KEY": env("PAYDUNYA_PUBLIC_KEY", default=""),
    "PRIVATE_KEY": env("PAYDUNYA_PRIVATE_KEY", default=""),
    "TOKEN": env("PAYDUNYA_TOKEN", default=""),
    "MODE": "test",
}

PAYDUNYA_URLS = {
    "test": "https://paydunya.com",
    "live": "https://paydunya.com",
}


# PAYDUNYA_CANCEL_URL = "http://localhost:3000/commandes"
# PAYDUNYA_RETURN_URL = "http://localhost:3000/products"

# PAYDUNYA_WALLET_CANCEL_URL = "http://localhost:3000/customer/fedilites"
# PAYDUNYA_WALLET_SUCCESS_URL = "http://localhost:3000/customer/wallet"


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

paydunya.debug = True

# PAYDUNYA_CALLBACK_URL = "https://outrage-dealer-entrap.ngrok-free.dev/api/v1/paiements/ipn/"
PAYDUNYA_CALLBACK_URL = f"{BACKEND_URL}/api/v1/paiements/ipn/"
