from rest_framework import viewsets, permissions, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema
from .models import FraisLivraison, Delivery, Livreur
from .serializers import (
    FraisLivraisonSerializer, FraisLivraisonPublicSerializer, 
    DeliverySerializer, LivreurSerializer, DeliveryStatusHistorySerializer,
    ConfirmerReceptionSerializer
)
from .filters import DeliveryFilter, LivreurFilter
from .services import DeliveryService
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

    @extend_schema(
        summary="Assigner un livreur",
        description="Assigne un profil Livreur à la livraison et met à jour son statut vers ASSIGNED.",
        request={
            "application/json": {
                "type": "object", 
                "properties": {"livreur_id": {"type": "string", "format": "uuid"}}
            }
        },
        responses={200: DeliverySerializer}
    )
    @action(detail=True, methods=["post"], permission_classes=[IsPlatformAdmin])
    def assign_livreur(self, request, pk=None):
        delivery = self.get_object()
        livreur_id = request.data.get("livreur_id")
        
        if not livreur_id:
            return Response({"error": "Livreur ID requis"}, status=status.HTTP_400_BAD_REQUEST)
            
        livreur = get_object_or_404(Livreur, pk=livreur_id)
        
        try:
            delivery = DeliveryService.assign_livreur(delivery, livreur, user=request.user)
            return Response(DeliverySerializer(delivery).data)
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(
        summary="Mettre à jour le statut",
        description="Mise à jour du statut avec création d'une entrée dans l'historique.",
        request={
            "application/json": {
                "type": "object", 
                "properties": {
                    "status": {"type": "string"}, 
                    "notes": {"type": "string"}
                }
            }
        },
        responses={200: DeliverySerializer}
    )
    @action(detail=True, methods=["post"], permission_classes=[IsPlatformAdmin])
    def update_status(self, request, pk=None):
        delivery = self.get_object()
        new_status = request.data.get("status")
        notes = request.data.get("notes", "")
        
        if not new_status:
            return Response({"error": "Nouveau statut requis"}, status=status.HTTP_400_BAD_REQUEST)
            
        try:
            delivery = DeliveryService.update_status(delivery, new_status, user=request.user, notes=notes)
            return Response(DeliverySerializer(delivery).data)
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(
        summary="Historique de la livraison",
        description="Retourne l'historique des changements de statut d'une livraison.",
        responses={200: DeliveryStatusHistorySerializer(many=True)}
    )
    @action(detail=True, methods=["get"])
    def history(self, request, pk=None):
        delivery = self.get_object()
        history = delivery.status_history.all()
        return Response(DeliveryStatusHistorySerializer(history, many=True).data)

    @extend_schema(
        summary="Confirmer la réception (Client)",
        description="Permet au client de confirmer qu'il a bien reçu sa commande.",
        request=ConfirmerReceptionSerializer,
        responses={200: DeliverySerializer}
    )
    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated])
    def confirmer_reception(self, request, pk=None):
        delivery = self.get_object()
        
        # Vérification d'autorisation stricte (le client ne peut confirmer que SA livraison)
        if delivery.order.user != request.user:
            return Response(
                {"error": "Vous n'êtes pas autorisé à confirmer cette livraison."}, 
                status=status.HTTP_403_FORBIDDEN
            )

        serializer = ConfirmerReceptionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        notes_client = serializer.validated_data.get("notes", "")
        final_notes = f"Réception confirmée par le client. {notes_client}".strip()

        try:
            # On utilise le status constant string depuis models
            from .models import DeliveryStatus
            delivery = DeliveryService.update_status(
                delivery, 
                DeliveryStatus.DELIVERED, 
                user=request.user, 
                notes=final_notes
            )
            
            # (Optionnel) Ici on pourrait faire: NotificationService.notify_admin_reception_confirmed(delivery)
            
            return Response(DeliverySerializer(delivery).data)
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)



# ─────────────────────────────────────────────────────────────────────────────
# LIVREUR VIEWSET
# ─────────────────────────────────────────────────────────────────────────────

class LivreurViewSet(viewsets.ModelViewSet):
    """
    CRUD complet pour la gestion des livreurs partenaires.

    Accès intégralement restreint à IsPlatformAdmin, y compris en lecture (GET).
    Justification : la liste des livreurs contient des données personnelles
    (téléphone, email) et ne doit jamais être exposée publiquement.
    Ceci diffère de FraisLivraisonViewSet dont le GET est public (données non PII).

    Suppression physique interdite si le livreur est référencé par une livraison :
    perform_destroy applique une désactivation logique (is_active=False) à la place,
    cohérente avec la présence de is_active sur BaseModel.
    """

    serializer_class = LivreurSerializer
    permission_classes = [IsPlatformAdmin]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = LivreurFilter
    search_fields = ["nom", "prenom", "telephone", "email"]
    ordering_fields = ["nom", "created_at"]
    ordering = ["nom", "prenom"]

    def get_queryset(self):
        """
        Retourne tous les livreurs avec prefetch du compte utilisateur associé.
        Pas de filtre implicite sur is_active : l'admin doit voir les livreurs
        désactivés pour pouvoir les réactiver.
        """
        return Livreur.objects.all().select_related("user")

    @extend_schema(
        summary="Lister les livreurs",
        description=(
            "Retourne la liste paginée des livreurs. "
            "Filtrable par statut, type de véhicule et zone. "
            "Recherche sur nom, prénom, téléphone et email. "
            "Accès réservé aux administrateurs de la plateforme."
        ),
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        summary="Créer un livreur",
        description="Crée un nouveau profil livreur. Accès réservé aux administrateurs.",
    )
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @extend_schema(
        summary="Détail d'un livreur",
        description="Retourne le détail complet d'un livreur. Accès réservé aux administrateurs.",
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @extend_schema(
        summary="Modifier un livreur",
        description="Mise à jour complète d'un profil livreur. Accès réservé aux administrateurs.",
    )
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    @extend_schema(
        summary="Modifier partiellement un livreur",
        description="Mise à jour partielle d'un profil livreur. Accès réservé aux administrateurs.",
    )
    def partial_update(self, request, *args, **kwargs):
        return super().partial_update(request, *args, **kwargs)

    @extend_schema(
        summary="Désactiver un livreur",
        description=(
            "Désactive logiquement le livreur (is_active=False) au lieu de le supprimer "
            "physiquement. Ceci préserve l'historique des livraisons passées. "
            "Accès réservé aux administrateurs."
        ),
    )
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)

    def perform_destroy(self, instance):
        """
        Désactivation logique à la place de la suppression physique.

        Même si le livreur n'est référencé par aucune livraison, on applique
        systématiquement la désactivation logique pour conserver l'intégrité
        de l'historique et permettre une réactivation future.
        """
        instance.is_active = False
        instance.save(update_fields=["is_active", "updated_at"])
