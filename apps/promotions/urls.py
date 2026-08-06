

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    ActivePromoCodesView,
    ValidatePromoCodeView,
    ApplyPromoCodeView,
    ActiveFlashSalesView,
    ActiveBannersView,
    AdminPromoCodeViewSet,
    AdminFlashSaleViewSet,
    AdminBannerViewSet,
    ActivePacksViewSet,
    AdminPackViewSet,
)

# Router public
public_router = DefaultRouter()
public_router.register(r"packs-actifs", ActivePacksViewSet, basename="active-packs")

# Router admin
admin_router = DefaultRouter()
admin_router.register(r"codes-promo", AdminPromoCodeViewSet, basename="admin-promo-codes")
admin_router.register(r"ventes-solde", AdminFlashSaleViewSet, basename="admin-ventes-solde")
admin_router.register(r"recommendations", AdminBannerViewSet, basename="admin-recommendations")
admin_router.register(r"packs", AdminPackViewSet, basename="admin-packs")

urlpatterns = [
    # Public
    path("codes-promo-actifs/", ActivePromoCodesView.as_view(), name="active-promo-codes"),

    path("codes-promo/validate/", ValidatePromoCodeView.as_view(), name="validate-promo-code"),

    # path("codes-promo/apply/", ApplyPromoCodeView.as_view(), name="apply-promo-code"),
    
    path("soldes-actifs/", ActiveFlashSalesView.as_view(), name="active-flash-sales"),

    path("recommendations-actives/", ActiveBannersView.as_view(), name="active-banners"),
    
    # Public ViewSets
    path("", include(public_router.urls)),

    # Admin
    path("admin/", include(admin_router.urls)),
]