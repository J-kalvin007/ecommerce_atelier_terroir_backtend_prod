from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.urls import include
from django.urls import path
from django.views import defaults as default_views
from django.views.generic import TemplateView
from drf_spectacular.views import SpectacularAPIView
from drf_spectacular.views import SpectacularSwaggerView
from rest_framework.authtoken.views import obtain_auth_token
from ecommerce_backend.users.auth_views import CustomLoginView
from ecommerce_backend.users.resend_email_view import ForceResendEmailView
from ecommerce_backend.users.password_reset_views import CustomPasswordResetConfirmView
from config.api_views import api_v1_root





urlpatterns = [
    path("", TemplateView.as_view(template_name="pages/home.html"), name="home"),
    path(
        "about/",
        TemplateView.as_view(template_name="pages/about.html"),
        name="about",
    ),
    # Django Admin, use {% url 'admin:index' %}
    path(settings.ADMIN_URL, admin.site.urls),
    # User management
    path("users/", include("ecommerce_backend.users.urls", namespace="users")),
    path("accounts/", include("allauth.urls")),
    
    
    # Your stuff: custom urls includes go here
    # ...
    # Media files
    *static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT),


    # PRIORITAIRE : Vue custom qui bypass dj-rest-auth/allauth pour la confirmation du reset.
    # Doit être déclarée AVANT l'include "dj_rest_auth.urls" pour avoir la priorité.
    path(
        "api/auth/password/reset/confirm/",
        CustomPasswordResetConfirmView.as_view(),
        name="custom_password_reset_confirm",
    ),

    path(
        "api/auth/",
        include("dj_rest_auth.urls")
    ),



    path(
        "api/auth/registration/",
        include("dj_rest_auth.registration.urls")
    ),

    # Vue custom de renvoi d'email — bypasse le cooldown allauth
    path(
        "api/auth/registration/force-resend-email/",
        ForceResendEmailView.as_view(),
        name="force-resend-email"
    ),

    path(
        "api/v1/",
        api_v1_root,
        name="api-v1-root"
    ),

    path(
        "api/v1/catalog/",
        include("apps.catalog.urls")
    ),


    path(
        "api/v1/commandes/",
        include("apps.commandes.urls")
    ),


    path(
        "api/v1/paiements/",
        include("apps.paiements.urls")
    ),

    path(
        "api/v1/promotions/",
        include("apps.promotions.urls")
    ),


    path(
        "api/v1/fidelites/", 
        include("apps.fidelites.urls")
    ),    

    path(
        "api/v1/livraisons/",
        include("apps.livraisons.urls")
    ),

    path(
        "api/v1/notifications/",
        include("apps.notifications.urls")
    ),
]

if settings.DEBUG:
    # Static file serving when using Gunicorn + Uvicorn for local web socket development
    urlpatterns += staticfiles_urlpatterns()


# API URLS
urlpatterns += [
    
    # API base url
    path("api/", include("config.api_router")),
    
    # DRF auth token
    path("api/auth-token/", obtain_auth_token, name="obtain_auth_token"),
    
    path("api/schema/", SpectacularAPIView.as_view(), name="api-schema"),
    
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="api-schema"),
        name="api-docs",
    ),

    path(
        "api/connexion/",
        CustomLoginView.as_view(),
        name="rest_login",
    ),

]


if settings.DEBUG:
    # This allows the error pages to be debugged during development, just visit
    # these url in browser to see how these error pages look like.
    urlpatterns += [
        
        path(
            "400/",
            default_views.bad_request,
            kwargs={"exception": Exception("Bad Request!")},
        ),
        
        path(
            "403/",
            default_views.permission_denied,
            kwargs={"exception": Exception("Permission Denied")},
        ),
        
        path(
            "404/",
            default_views.page_not_found,
            kwargs={"exception": Exception("Page not Found")},
        ),
        
        path("500/", default_views.server_error),
    ]

    if "debug_toolbar" in settings.INSTALLED_APPS:
        import debug_toolbar

        urlpatterns = [
            path("__debug__/", include(debug_toolbar.urls)),
            *urlpatterns,
        ]
