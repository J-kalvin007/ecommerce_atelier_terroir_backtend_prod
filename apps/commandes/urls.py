from django.urls import path

from apps.commandes.views import (
    AdminOrderDetailAPIView,
    AdminOrderListAPIView,
    AdminOrderStatusAPIView,
    CheckoutAPIView,
    MyOrderListAPIView,
    OrderDetailAPIView,
    OrderHistoryAPIView,
    OrderCancelView,
    CartAPIView,
    CartItemAPIView,
    CartItemDetailAPIView,
)

app_name = "commandes"

urlpatterns = [

    # ==================================================
    # CART
    # ==================================================
    path(
        "cart/",
        CartAPIView.as_view(),
        name="cart",
    ),
    path(
        "cart/items/",
        CartItemAPIView.as_view(),
        name="cart-items",
    ),
    path(
        "cart/items/<uuid:product_id>/",
        CartItemDetailAPIView.as_view(),
        name="cart-item-detail",
    ),

    # ==================================================
    # CLIENT
    # ==================================================
    path(
        "validate-commandes/",
        CheckoutAPIView.as_view(),
        name="checkout",
    ),

    path(
        "mes-commandes/",
        MyOrderListAPIView.as_view(),
        name="my-orders",
    ),

    path(
        "mes-commandes/<str:reference>/",
        OrderDetailAPIView.as_view(),
        name="order-detail",
    ),

    path(
        "mes-commandes/<str:reference>/historique/",
        OrderHistoryAPIView.as_view(),
        name="order-history",
    ),

    path(
        "mes-commandes/<str:reference>/cancel/",
        OrderCancelView.as_view(),
        name="order-cancel",
    ),

    # ==================================================
    # ADMIN
    # ==================================================
    path(
        "admin/all-commandes/",
        AdminOrderListAPIView.as_view(),
        name="admin-orders",
    ),

    path(
        "admin/commandes/<str:reference>/",
        AdminOrderDetailAPIView.as_view(),
        name="admin-order-detail",
    ),
    
    path(
        "admin/commandes/<str:reference>/status/",
        AdminOrderStatusAPIView.as_view(),
        name="admin-order-status",
    ),
]