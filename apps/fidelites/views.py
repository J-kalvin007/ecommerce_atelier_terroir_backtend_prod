"""
Vues DRF pour le module de fidélisation.

Endpoints :
- GET  /me/ : profil loyalty de l'utilisateur connecté
- GET  /tiers/ : tous les paliers (public)
- POST /points/redeem/ : dépenser des points
- GET  /events/ : journal des événements
- GET  /referral/ : code de parrainage + stats
- Admin : gestion des profils, ajustement manuel
"""
from django.db import models
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.permissions import IsPlatformAdmin
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiResponse, inline_serializer
from rest_framework import serializers
from .models import LoyaltyTier, LoyaltyProfile, LoyaltyEvent, PointValue, LoyaltyRewardRule
from .serializers import (
    TierSerializer,
    AdminTierSerializer,
    LoyaltyProfileSerializer,
    LoyaltyEventSerializer,
    RedeemPointsSerializer,
    AdminAdjustPointsSerializer,
    PointValueSerializer,
    AdminPointValueSerializer,
    LoyaltyRewardRuleSerializer,
)
from .services import LoyaltyService


class MyLoyaltyProfileView(APIView):
    """
    GET /api/v1/loyalty/me/
    Profil de fidélité complet de l'utilisateur connecté.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Mon profil de fidélité",
        description="Profil de fidélité complet de l'utilisateur connecté.",
        responses={
            200: LoyaltyProfileSerializer,
            404: OpenApiResponse(description="Profil de fidélité introuvable.")
        }
    )
    def get(self, request):
        try:
            profile = LoyaltyProfile.objects.select_related("tier").get(
                user=request.user
            )
        except LoyaltyProfile.DoesNotExist:
            return Response(
                {"detail": "Profil de fidélité introuvable."},
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = LoyaltyProfileSerializer(profile)
        return Response(serializer.data)


class TiersListView(APIView):
    """
    GET /api/v1/fidelites/tiers/
    Liste de tous les paliers avec leurs avantages (public).
    """
    permission_classes = [AllowAny]

    @extend_schema(
        summary="Liste des paliers",
        description="Liste de tous les paliers de fidélité avec leurs avantages.",
        responses=TierSerializer(many=True)
    )
    def get(self, request):
        tiers = LoyaltyTier.objects.all().order_by("min_points")
        serializer = TierSerializer(tiers, many=True)
        return Response(serializer.data)


class PointValueAPIView(APIView):
    """
    GET /api/v1/fidelites/point-value/
    Récupère la configuration actuelle de la valeur des points (public).
    """
    permission_classes = [AllowAny]

    @extend_schema(
        summary="Valeur actuelle des points",
        description="Récupère la configuration active (valeur en FCFA, durée de validité).",
        responses={
            200: PointValueSerializer,
            404: OpenApiResponse(description="Aucune configuration active n'a été trouvée.")
        }
    )
    def get(self, request):
        from .models import PointValue
        from .serializers import PointValueSerializer
        
        point_value = PointValue.objects.filter(is_active=True).first()
        if not point_value:
            return Response(
                {"detail": "Aucune configuration de valeur de point active trouvée."},
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = PointValueSerializer(point_value)
        return Response(serializer.data)


class RedeemPointsView(APIView):
    """
    POST /api/v1/loyalty/points/redeem/
    Dépenser des points de fidélité sur une commande.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Dépenser des points",
        description="Dépenser des points de fidélité sur une commande.",
        request=RedeemPointsSerializer,
        responses={
            200: inline_serializer(
                name="RedeemPointsResponse",
                fields={
                    "success": serializers.BooleanField(),
                    "points_spent": serializers.IntegerField(),
                    "discount_amount": serializers.CharField(),
                    "order_total_after": serializers.CharField(),
                }
            ),
            400: OpenApiResponse(description="Erreur de validation ou points insuffisants.")
        }
    )
    def post(self, request):
        serializer = RedeemPointsSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)

        from apps.commandes.models import Order
        order = Order.objects.get(pk=serializer.validated_data["order_id"])

        try:
            discount = LoyaltyService.redeem_points(
                user=request.user,
                order=order,
                points_to_spend=serializer.validated_data["points_to_spend"],
            )
            return Response({
                "success": True,
                "points_spent": serializer.validated_data["points_to_spend"],
                "discount_amount": str(discount),
                "order_total_after": str(order.total_final),
            })
        except ValueError as e:
            return Response(
                {"detail": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )


class LoyaltyEventsView(ListAPIView):
    """
    GET /api/v1/loyalty/events/
    Journal paginé des événements de points de l'utilisateur connecté.
    """
    permission_classes = [IsAuthenticated]
    serializer_class = LoyaltyEventSerializer

    @extend_schema(
        summary="Journal des événements",
        description="Journal paginé des événements de points de l'utilisateur connecté.",
        responses=LoyaltyEventSerializer(many=True)
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        return LoyaltyEvent.objects.filter(
            user=self.request.user
        ).order_by("-created_at")



# ─── Admin ────────────────────────────────────────────────────────────────

class AdminLoyaltyTierViewSet(viewsets.ModelViewSet):
    """
    CRUD admin pour les paliers de fidélité.
    """
    queryset = LoyaltyTier.objects.all().order_by("min_points")
    serializer_class = AdminTierSerializer
    permission_classes = [IsPlatformAdmin]
    search_fields = ("name",)


class AdminLoyaltyProfileViewSet(viewsets.ModelViewSet):
    """
    CRUD admin pour les profils de fidélité.
    GET    /api/v1/loyalty/admin/profiles/
    PATCH  /api/v1/loyalty/admin/profiles/{id}/
    """
    queryset = LoyaltyProfile.objects.select_related("user", "tier").all()
    serializer_class = LoyaltyProfileSerializer
    permission_classes = [IsPlatformAdmin]
    search_fields = ("user__email",)

    @extend_schema(
        summary="Ajuster les points (Admin)",
        description="Ajustement manuel de points pour un utilisateur par un administrateur.",
        request=AdminAdjustPointsSerializer,
        responses={
            200: inline_serializer(
                name="AdminAdjustPointsResponse",
                fields={
                    "success": serializers.BooleanField(),
                    "user_email": serializers.EmailField(),
                    "points_adjusted": serializers.IntegerField(),
                    "new_balance": serializers.IntegerField(),
                }
            ),
            404: OpenApiResponse(description="Utilisateur introuvable.")
        }
    )


    @action(detail=False, methods=["post"])
    def adjust_points(self, request):
        """
        POST /api/v1/loyalty/admin/adjust-points/
        Ajustement manuel de points par un administrateur.
        """
        serializer = AdminAdjustPointsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user_id = serializer.validated_data["user_id"]
        points = serializer.validated_data["points"]
        reason_text = serializer.validated_data["reason"]

        from django.contrib.auth import get_user_model
        User = get_user_model()

        try:
            profile = LoyaltyProfile.objects.select_related("user").get(pk=user_id)
            user = profile.user
        except LoyaltyProfile.DoesNotExist:
            try:
                user = User.objects.get(pk=user_id)
            except User.DoesNotExist:
                return Response(
                    {"detail": "Utilisateur ou profil introuvable."},
                    status=status.HTTP_404_NOT_FOUND,
                )

        from django.db import transaction
        with transaction.atomic():
            profile = LoyaltyProfile.objects.select_for_update().get(user=user)
            profile.points_balance = models.F("points_balance") + points
            if points > 0:
                profile.total_points_gagne = models.F("total_points_gagne") + points
            profile.save(update_fields=["points_balance", "total_points_gagne", "updated_at"])
            profile.refresh_from_db()

            LoyaltyEvent.objects.create(
                user=user,
                points_delta=points,
                new_points_balance_after=profile.points_balance,
                reason=LoyaltyEvent.Reason.ADMIN_ADJUSTMENT,
                description=reason_text,
            )

        return Response({
            "success": True,
            "user_email": user.email,
            "points_adjusted": points,
            "new_balance": profile.points_balance,
        })


from drf_spectacular.utils import extend_schema_view
from .models import PointValue, LoyaltyRewardRule
from .serializers import AdminPointValueSerializer, LoyaltyRewardRuleSerializer


@extend_schema_view(
    list=extend_schema(summary="Liste des valeurs de points", description="Affiche toutes les configurations de valeurs de points (Admin)."),
    retrieve=extend_schema(summary="Détail d'une valeur", description="Affiche les détails d'une configuration de valeur de points."),
    create=extend_schema(summary="Créer une valeur", description="Ajoute une nouvelle configuration de point."),
    update=extend_schema(summary="Modifier une valeur", description="Mise à jour complète d'une configuration."),
    partial_update=extend_schema(summary="Modifier partiellement", description="Mise à jour partielle d'une configuration."),
    destroy=extend_schema(summary="Supprimer une valeur", description="Supprime une configuration de point.")
)
class AdminPointValueViewSet(viewsets.ModelViewSet):
    """
    CRUD admin pour la valeur des points.
    """
    queryset = PointValue.objects.all()
    serializer_class = AdminPointValueSerializer
    permission_classes = [IsPlatformAdmin]


@extend_schema_view(
    list=extend_schema(summary="Liste des bénéfices", description="Affiche toutes les règles de gain (Bénéfices) (Admin)."),
    retrieve=extend_schema(summary="Détail d'un bénéfice", description="Affiche les détails d'une règle de gain."),
    create=extend_schema(summary="Créer un bénéfice", description="Ajoute une nouvelle règle de gain (tranche de montant -> points)."),
    update=extend_schema(summary="Modifier un bénéfice", description="Mise à jour complète d'une règle."),
    partial_update=extend_schema(summary="Modifier partiellement", description="Mise à jour partielle d'une règle."),
    destroy=extend_schema(summary="Supprimer un bénéfice", description="Supprime une règle de gain.")
)
class AdminLoyaltyRewardRuleViewSet(viewsets.ModelViewSet):
    """
    CRUD admin pour les règles de gain (Bénéfices).
    """
    queryset = LoyaltyRewardRule.objects.all().order_by("montant_min")
    serializer_class = LoyaltyRewardRuleSerializer
    permission_classes = [IsPlatformAdmin]