from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    RecetteViewSet,
    AdminRecetteViewSet,
)

app_name = "recettes"

# Router public
public_router = DefaultRouter()
public_router.register(r"", RecetteViewSet, basename="recettes")

# Router admin
admin_router = DefaultRouter()
admin_router.register(r"recettes", AdminRecetteViewSet, basename="admin-recettes")

urlpatterns = [
    # Public
    path("", include(public_router.urls)),

    # Admin
    path("admin/", include(admin_router.urls)),
]
