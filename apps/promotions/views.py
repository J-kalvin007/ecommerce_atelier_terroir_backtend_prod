"""
Vues DRF pour le module promotions.

Endpoints :
- Publics : liste codes, flash sales, bannières
- Authentifiés : validation et application de code promo
- Admin : CRUD complet
"""
import uuid
from django.db import models
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.permissions import IsPlatformAdmin
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiResponse, OpenApiParameter, inline_serializer
from rest_framework import serializers
from .exceptions import PromoCodeError
from .models import PromoCode, Soldes, Banner, Pack
from .serializers import (
    PromoCodeListSerializer,
    ValidateCodeSerializer,
    ApplyCodeSerializer,
    SoldesSerializer,
    BannerSerializer,
    AdminPromoCodeSerializer,
    AdminSoldesSerializer,
    AdminBannerSerializer,
    PackSerializer,
    AdminPackSerializer,
)
from .services import PromoService


# ─── Public ────────────────────────────────────────────────────────────────

class ActivePromoCodesView(APIView):
    """
    GET /api/v1/promotions/codes/
    Liste des codes promo actifs (public).
    """
    permission_classes = [AllowAny]

    @extend_schema(
        summary="Codes promo actifs",
        description="Liste des codes promo actifs et publics.",
        responses=PromoCodeListSerializer(many=True)
    )
    def get(self, request):
        from django.utils import timezone
        now = timezone.now()
        codes = PromoCode.objects.filter(
            is_active=True,
            starts_at__lte=now,
        ).exclude(
            expires_at__isnull=False,
            expires_at__lt=now,
        ).order_by("-created_at")[:20]

        serializer = PromoCodeListSerializer(codes, many=True)
        return Response(serializer.data)


class ValidatePromoCodeView(APIView):
    """
    POST /api/v1/promotions/codes/validate/
    Valide un code promo sans l'appliquer.
    Retourne la réduction potentielle.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Valider un code promo",
        description="Valide un code promo sans l'appliquer et retourne la réduction potentielle.",
        request=ValidateCodeSerializer,
        responses={
            200: inline_serializer(
                name="ValidatePromoResponse",
                fields={
                    "valid": serializers.BooleanField(),
                    "code": serializers.CharField(),
                    "type": serializers.CharField(),
                    "value": serializers.CharField(),
                    "discount_amount": serializers.CharField(),
                    "description": serializers.CharField(),
                }
            ),
            400: inline_serializer(
                name="ValidatePromoErrorResponse",
                fields={
                    "valid": serializers.BooleanField(),
                    "error_code": serializers.CharField(),
                    "detail": serializers.CharField(),
                }
            )
        }
    )
    def post(self, request):
        serializer = ValidateCodeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            promo, discount = PromoService.validate_code(
                code=serializer.validated_data["code"],
                user=request.user,
                cart_total=serializer.validated_data["cart_total"],
            )
            return Response({
                "valid": True,
                "code": promo.code,
                "type": promo.type,
                "value": str(promo.value),
                "discount_amount": str(discount),
                "description": promo.description,
            })
        except PromoCodeError as e:
            return Response({
                "valid": False,
                "error_code": e.code,
                "detail": e.message,
            }, status=status.HTTP_400_BAD_REQUEST)


class ApplyPromoCodeView(APIView):
    """
    POST /api/v1/promotions/codes/apply/
    Applique un code promo à une commande.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Appliquer un code promo",
        description="Applique un code promo à une commande existante.",
        request=ApplyCodeSerializer,
        responses={
            200: inline_serializer(
                name="ApplyPromoResponse",
                fields={
                    "applied": serializers.BooleanField(),
                    "code": serializers.CharField(),
                    "discount_amount": serializers.CharField(),
                    "order_total_after": serializers.CharField(),
                }
            ),
            400: inline_serializer(
                name="ApplyPromoErrorResponse",
                fields={
                    "applied": serializers.BooleanField(),
                    "error_code": serializers.CharField(),
                    "detail": serializers.CharField(),
                }
            ),
            404: OpenApiResponse(description="Commande introuvable.")
        }
    )
    def post(self, request):
        serializer = ApplyCodeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        from apps.commandes.models import Order
        try:
            order = Order.objects.get(
                pk=serializer.validated_data["order_id"],
                user=request.user,
            )
        except Order.DoesNotExist:
            return Response(
                {"detail": "Commande introuvable."},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            # Valider
            promo, discount = PromoService.validate_code(
                code=serializer.validated_data["code"],
                user=request.user,
                cart_total=order.total_final,  # Avant réduction
            )
            # Appliquer
            discount_applied = PromoService.apply_code(
                promo_code=promo,
                user=request.user,
                order=order,
                discount_amount=discount,
            )
            return Response({
                "applied": True,
                "code": promo.code,
                "discount_amount": str(discount_applied),
                "order_total_after": str(order.total_final),
            })
        except PromoCodeError as e:
            return Response({
                "applied": False,
                "error_code": e.code,
                "detail": e.message,
            }, status=status.HTTP_400_BAD_REQUEST)


class ActiveFlashSalesView(APIView):
    """
    GET /api/v1/promotions/soldes-actifs/
    Ventes en solde en cours (public).
    """
    permission_classes = [AllowAny]

    @extend_schema(
        summary="Ventes en solde actives",
        description="Liste des ventes en solde en cours.",
        responses=SoldesSerializer(many=True)
    )
    def get(self, request):
        flash_sales = PromoService.get_active_flash_sales()
        serializer = SoldesSerializer(
            flash_sales, many=True, context={"request": request}
        )
        return Response(serializer.data)




class ActiveBannersView(APIView):
    """
    GET /api/v1/promotions/recommandations-actives/
    Bannières publicitaires actives (public). Filtre optionnel ?type=CAROUSEL
    """
    permission_classes = [AllowAny]

    @extend_schema(
        summary="Bannières publicitaires actives",
        description="Liste des bannières publicitaires actives. Vous pouvez filtrer par type avec `?type=CAROUSEL`.",
        parameters=[
            OpenApiParameter(name="type", description="Filtre par type de bannière (ex: CAROUSEL, PROMO, INFO)", required=False, type=str)
        ],
        responses=BannerSerializer(many=True)
    )
    def get(self, request):
        banner_type = request.query_params.get("type")
        banners = PromoService.get_active_banners(banner_type=banner_type)
        serializer = BannerSerializer(
            banners, many=True, context={"request": request}
        )
        return Response(serializer.data)


class ActivePacksViewSet(viewsets.ReadOnlyModelViewSet):
    """
    GET /api/v1/promotions/packs-actifs/
    Liste des packs promotionnels actifs (public).
    """
    permission_classes = [AllowAny]
    serializer_class = PackSerializer
    lookup_field = "slug"
    
    @extend_schema(
        summary="Liste des packs actifs",
        description="Renvoie la liste des packs promotionnels actuellement actifs."
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        summary="Détails d'un pack",
        description="Renvoie les détails d'un pack promotionnel, y compris ses composants."
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    def get_queryset(self):
        return Pack.objects.filter(is_active=True).prefetch_related(
            "items__product_variant__product__category",
            "items__product_variant__product__images"
        ).order_by("-created_at")


# ─── Admin ────────────────────────────────────────────────────────────────

@extend_schema_view(
    list=extend_schema(summary="Lister les codes promo (Admin)", description="Retourne la liste complète de tous les codes promotionnels. Accès réservé aux administrateurs de la plateforme."),
    retrieve=extend_schema(summary="Détails d'un code promo (Admin)", description="Retourne les détails d'un code promotionnel spécifique par son ID."),
    create=extend_schema(summary="Créer un code promo (Admin)", description="Permet de créer un nouveau code promotionnel."),
    update=extend_schema(summary="Mettre à jour un code promo (Admin)", description="Met à jour l'intégralité d'un code promotionnel."),
    partial_update=extend_schema(summary="Mettre à jour partiellement un code promo (Admin)", description="Met à jour partiellement les champs d'un code promotionnel."),
    destroy=extend_schema(summary="Supprimer un code promo (Admin)", description="Supprime un code promotionnel de manière permanente.")
)
class AdminPromoCodeViewSet(viewsets.ModelViewSet):
    """
    CRUD admin pour les codes promo.
    POST   /api/v1/promotions/admin/codes-promo/
    GET    /api/v1/promotions/admin/codes-promo/{id}/
    """
    queryset = PromoCode.objects.all().order_by("-created_at")
    serializer_class = AdminPromoCodeSerializer
    permission_classes = [IsPlatformAdmin]

    # @extend_schema(
    #     summary="Dupliquer un code promo",
    #     description="Crée une copie d'un code promo existant avec un nouveau code généré aléatoirement.",
    #     responses={201: AdminPromoCodeSerializer}
    # )

    # @action(detail=True, methods=["post"])
    # def duplicate(self, request, pk=None):
    #     """Duplique un code promo existant."""
    #     original = self.get_object()
    #     original.pk = None
    #     original.code = f"{original.code}-COPY-{uuid.uuid4().hex[:4].upper()}"
    #     original.number_times_used = 0
    #     original.save()
    #     serializer = self.get_serializer(original)
    #     return Response(serializer.data, status=status.HTTP_201_CREATED)



    @extend_schema(
        summary="Désactiver les codes expirés",
        description="Désactive en masse tous les codes promotionnels dont la date d'expiration est dépassée.",
        responses={
            200: inline_serializer(
                name="DeactivateExpiredResponse",
                fields={
                    "deactivated": serializers.IntegerField(help_text="Nombre de codes désactivés.")
                }
            )
        }
    )

    @action(detail=False, methods=["post"])
    def deactivate_expired(self, request):
        """Désactive en masse tous les codes expirés."""
        from django.utils import timezone
        count = PromoCode.objects.filter(
            is_active=True,
            expires_at__lt=timezone.now(),
        ).update(is_active=False)
        return Response({"deactivated": count})




@extend_schema_view(
    list=extend_schema(summary="Lister les ventes flash (Admin)", description="Retourne la liste de toutes les ventes flash/soldes. Accès réservé aux administrateurs de la plateforme."),
    retrieve=extend_schema(summary="Détails d'une vente flash (Admin)", description="Retourne les détails d'une vente flash spécifique."),
    create=extend_schema(summary="Créer une vente flash (Admin)", description="Permet de créer une nouvelle vente flash."),
    update=extend_schema(summary="Mettre à jour une vente flash (Admin)", description="Met à jour l'intégralité d'une vente flash."),
    partial_update=extend_schema(summary="Mettre à jour partiellement une vente flash (Admin)", description="Met à jour partiellement une vente flash."),
    destroy=extend_schema(summary="Supprimer une vente flash (Admin)", description="Supprime une vente flash de manière permanente.")
)
class AdminFlashSaleViewSet(viewsets.ModelViewSet):
    """CRUD admin pour les ventes en solde."""
    queryset = Soldes.objects.all().order_by("-starts_at")
    serializer_class = AdminSoldesSerializer
    permission_classes = [IsPlatformAdmin]




@extend_schema_view(
    list=extend_schema(summary="Lister les bannières (Admin)", description="Retourne la liste de toutes les bannières publicitaires. Accès réservé aux administrateurs de la plateforme."),
    retrieve=extend_schema(summary="Détails d'une bannière (Admin)", description="Retourne les détails d'une bannière spécifique."),
    create=extend_schema(summary="Créer une bannière (Admin)", description="Permet de créer une nouvelle bannière."),
    update=extend_schema(summary="Mettre à jour une bannière (Admin)", description="Met à jour l'intégralité d'une bannière."),
    partial_update=extend_schema(summary="Mettre à jour partiellement une bannière (Admin)", description="Met à jour partiellement une bannière."),
    destroy=extend_schema(summary="Supprimer une bannière (Admin)", description="Supprime une bannière de manière permanente.")
)
class AdminBannerViewSet(viewsets.ModelViewSet):
    """CRUD admin pour les bannières."""
    queryset = Banner.objects.all().order_by("banner_type", "position")
    serializer_class = AdminBannerSerializer
    permission_classes = [IsPlatformAdmin]


@extend_schema_view(
    list=extend_schema(summary="Lister les packs promotionnels (Admin)", description="Retourne la liste de tous les packs promotionnels. Accès réservé aux administrateurs de la plateforme."),
    retrieve=extend_schema(summary="Détails d'un pack promotionnel (Admin)", description="Retourne les détails d'un pack promotionnel spécifique via son slug."),
    create=extend_schema(summary="Créer un pack promotionnel (Admin)", description="Permet de créer un nouveau pack promotionnel avec ses produits associés."),
    update=extend_schema(summary="Mettre à jour un pack promotionnel (Admin)", description="Met à jour l'intégralité d'un pack promotionnel."),
    partial_update=extend_schema(summary="Mettre à jour partiellement un pack promotionnel (Admin)", description="Met à jour partiellement un pack promotionnel."),
    destroy=extend_schema(summary="Supprimer un pack promotionnel (Admin)", description="Supprime un pack promotionnel de manière permanente.")
)
class AdminPackViewSet(viewsets.ModelViewSet):
    """CRUD admin pour les packs promotionnels."""
    queryset = Pack.objects.all().order_by("-created_at")
    serializer_class = AdminPackSerializer
    permission_classes = [IsPlatformAdmin]
    lookup_field = "slug"