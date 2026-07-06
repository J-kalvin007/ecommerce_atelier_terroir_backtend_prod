from django.urls import NoReverseMatch
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.reverse import reverse

def safe_reverse(viewname, request, format, default=None):
    try:
        return reverse(viewname, request=request, format=format)
    except NoReverseMatch:
        return default

@api_view(["GET"])
@permission_classes([AllowAny])
def api_v1_root(request, format=None):
    """
    Point d'entrée principal pour l'API v1 de la plateforme d'e-commerce.
    Affiche la liste ordonnée et catégorisée de tous les modules d'API disponibles.
    """
    endpoints = {}

    # --- Authentification, Utilisateurs & Documentation ---
    endpoints["auth"] = {
        "login": safe_reverse("rest_login", request, format),
        "obtain-token": safe_reverse("obtain_auth_token", request, format),
        "api-schema": safe_reverse("api-schema", request, format),
        "api-docs": safe_reverse("api-docs", request, format),
        "users": safe_reverse("api:user-list", request, format),
    }

    # --- Catalogue de produits ---
    endpoints["catalog"] = {
        "products": safe_reverse("catalog:products-list", request, format),
        "categories": safe_reverse("catalog:categories-list", request, format),
        "admin-products": safe_reverse("catalog:admin-products-list", request, format),
        "admin-categories": safe_reverse("catalog:admin-categories-list", request, format),
        "admin-product-images": safe_reverse("catalog:admin-product-images-list", request, format),
        "admin-product-variants": safe_reverse("catalog:admin-product-variants-list", request, format),
        "favorites-my": safe_reverse("catalog:my-favorites", request, format),
    }

    # --- Commandes ---
    endpoints["commandes"] = {
        "checkout": safe_reverse("commandes:checkout", request, format),
        "my-orders": safe_reverse("commandes:my-orders", request, format),
        "admin-orders": safe_reverse("commandes:admin-orders", request, format),
    }

    # --- Paiements & Portefeuille ---
    endpoints["paiements"] = {
        "wallet-balance": safe_reverse("wallet-balance", request, format),
        "wallet-deposit": safe_reverse("wallet-deposit", request, format),
        "wallet-pay": safe_reverse("wallet-pay", request, format),
        "wallet-transactions": safe_reverse("wallet-transactions", request, format),
        "payment-initiate": safe_reverse("payment-initiate", request, format),
        "my-transfers": safe_reverse("my-transfers", request, format),
        "admin-withdraw": safe_reverse("admin-withdraw", request, format),
    }

    # --- Codes Promos & Ventes Flash ---
    endpoints["promotions"] = {
        "active-promo-codes": safe_reverse("active-promo-codes", request, format),
        "validate-promo-code": safe_reverse("validate-promo-code", request, format),
        "apply-promo-code": safe_reverse("apply-promo-code", request, format),
        "active-flash-sales": safe_reverse("active-flash-sales", request, format),
        "active-banners": safe_reverse("active-banners", request, format),
        "admin-promo-codes": safe_reverse("admin-promo-codes-list", request, format),
        "admin-flash-sales": safe_reverse("admin-flash-sales-list", request, format),
        "admin-banners": safe_reverse("admin-banners-list", request, format),
    }

    # --- Fidélité & Parrainage ---
    endpoints["fidelites"] = {
        "my-profile": safe_reverse("my-loyalty-profile", request, format),
        "tiers": safe_reverse("loyalty-tiers", request, format),
        "points-redeem": safe_reverse("redeem-points", request, format),
        "events": safe_reverse("loyalty-events", request, format),
        "referral": safe_reverse("loyalty-referral", request, format),
        "admin-profiles": safe_reverse("admin-loyalty-profiles-list", request, format),
    }

    # Nettoyage des endpoints vides ou non-configurés
    clean_endpoints = {}
    for section, urls in endpoints.items():
        clean_urls = {k: v for k, v in urls.items() if v is not None}
        if clean_urls:
            clean_endpoints[section] = clean_urls

    return Response(clean_endpoints)
