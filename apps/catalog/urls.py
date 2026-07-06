from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import ToggleFavoriteView, MyFavoritesView, DeleteFavoriteView
from .views import RateProductView, ProductRatingDetailView, DeleteRatingView, MyRatingsView
from .views import (
    CategoryAdminViewSet,
    CategoryViewSet,
    ProductAdminViewSet,
    ProductImageAdminViewSet,
    ProductVariantAdminViewSet,
    ProductViewSet,
)

app_name = "catalog"

router = DefaultRouter()


# =====================================================
# PUBLIC API
# =====================================================

router.register(
    r"products",
    ProductViewSet,
    basename="products",
)

router.register(
    r"categories",
    CategoryViewSet,
    basename="categories",
)

# =====================================================
# ADMIN API
# =====================================================

router.register(
    r"admin/products",
    ProductAdminViewSet,
    basename="admin-products",
)

router.register(
    r"admin/categories",
    CategoryAdminViewSet,
    basename="admin-categories",
)

router.register(
    r"admin/product-images",
    ProductImageAdminViewSet,
    basename="admin-product-images",
)

router.register(
    r"admin/product-variants",
    ProductVariantAdminViewSet,
    basename="admin-product-variants",
)

urlpatterns = [
    path(
        "favorites-toggle/",
        ToggleFavoriteView.as_view(),
        name="favorites-toggle",
    ),

    path(
        "products/my-favorites/",
        MyFavoritesView.as_view(),
        name="my-favorites",
    ),

    path(
        "favorites-delete/<uuid:id>/",
        DeleteFavoriteView.as_view(),
        name="favorites-delete",
    ),


    path(
        "notes-products/",
        RateProductView.as_view(),
        name="ratings-rate",
    ),

    path(
        "notes-products/mes-notes/",
        MyRatingsView.as_view(),
        name="my-ratings",
    ),

    # path(
    #     "notes-products/<uuid:id>/",
    #     ProductRatingDetailView.as_view(),
    #     name="ratings-detail",
    # ),

    path(
        "notes-products/delete/<uuid:id>/",
        DeleteRatingView.as_view(),
        name="ratings-delete",
    ),

    # Le routeur doit être inclus à la fin pour éviter que `products/<pk>/` 
    # n'intercepte les routes spécifiques comme `products/my-favorites/`.
    path("", include(router.urls)),
]





