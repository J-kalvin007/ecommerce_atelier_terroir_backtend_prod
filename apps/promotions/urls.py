

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
)

# Router admin
admin_router = DefaultRouter()
admin_router.register(r"codes-promo", AdminPromoCodeViewSet, basename="admin-promo-codes")
admin_router.register(r"ventes-solde", AdminFlashSaleViewSet, basename="admin-ventes-solde")
admin_router.register(r"recommendations", AdminBannerViewSet, basename="admin-recommendations")

urlpatterns = [
    # Public
    path("codes-promo-actifs/", ActivePromoCodesView.as_view(), name="active-promo-codes"),

    path("codes-promo/validate/", ValidatePromoCodeView.as_view(), name="validate-promo-code"),

    # path("codes-promo/apply/", ApplyPromoCodeView.as_view(), name="apply-promo-code"),
    
    path("soldes-actifs/", ActiveFlashSalesView.as_view(), name="active-flash-sales"),

    path("recommendations-actives/", ActiveBannersView.as_view(), name="active-banners"),
    
    # Admin
    path("admin/", include(admin_router.urls)),
]