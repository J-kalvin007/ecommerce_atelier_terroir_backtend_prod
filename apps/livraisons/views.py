from rest_framework import viewsets, permissions, filters
from django_filters.rest_framework import DjangoFilterBackend
from .models import FraisLivraison, Delivery
from .serializers import FraisLivraisonSerializer, FraisLivraisonPublicSerializer, DeliverySerializer
from .filters import DeliveryFilter
from apps.core.permissions import IsPlatformAdmin, IsCustomer

class FraisLivraisonViewSet(viewsets.ModelViewSet):
    """
    Gestion des frais de livraison (Admin seulement, sauf GET public).
    """
    queryset = FraisLivraison.objects.all()
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ["created_at", "prix_livraison"]
    ordering = ["-created_at"]

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            permission_classes = [permissions.AllowAny]
        else:
            permission_classes = [IsPlatformAdmin]
        return [permission() for permission in permission_classes]

    def get_serializer_class(self):
        if self.action in ['list', 'retrieve']:
            user = self.request.user
            if not (user and user.is_authenticated and (user.is_superuser or getattr(user, 'role', '') == 'platform_admin')):
                return FraisLivraisonPublicSerializer
        return FraisLivraisonSerializer


class DeliveryViewSet(viewsets.ModelViewSet):
    """
    Gestion et suivi des livraisons.
    """
    serializer_class = DeliverySerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = DeliveryFilter
    search_fields = ["order__reference", "tracking_number", "delivery_address"]
    ordering_fields = ["created_at", "status", "estimated_delivery_date"]
    ordering = ["-created_at"]

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            # Seuls les admins peuvent modifier les livraisons
            permission_classes = [IsPlatformAdmin]
        else:
            # Tout utilisateur authentifié peut potentiellement voir ses propres livraisons
            permission_classes = [permissions.IsAuthenticated]
        return [permission() for permission in permission_classes]

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser or user.role == "platform_admin":
            return Delivery.objects.all().select_related("order", "delivery_person")
        
        # Pour les clients : on filtre sur les livraisons liées à leurs commandes
        return Delivery.objects.filter(order__user=user).select_related("order", "delivery_person")
