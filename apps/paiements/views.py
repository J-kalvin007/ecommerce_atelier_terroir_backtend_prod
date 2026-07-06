"""
Vues DRF pour le module de paiement.

Zéro logique métier : toute la logique est déléguée aux services.
"""
import logging
from rest_framework import status

logger = logging.getLogger(__name__)
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.permissions import IsPlatformAdmin, IsCustomer
from drf_spectacular.utils import extend_schema, OpenApiResponse, inline_serializer
from rest_framework import serializers
from .exceptions import (
    InsufficientBalanceError,
    PaymentGatewayError,
    WalletInactiveError,
)
from decimal import Decimal
from django.db.models import Sum

from .models import WalletTransaction, Payment, Wallet
from .serializers import (
    WalletSerializer,
    WalletTransactionSerializer,
    DepositSerializer,
    WalletPaySerializer,
    InitiatePaymentSerializer,
    PaymentSerializer,
    AdminWithdrawSerializer,
    OrderRefundSerializer,
    MyTransferSerializer,
    AdminWalletSerializer,
    AdminWalletStatusUpdateSerializer,
)
from .services import PaymentService, WalletService


class WalletBalanceView(RetrieveAPIView):
    """GET /api/v1/payments/wallet/ - Solde et statut du wallet de l'utilisateur."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Solde du Wallet",
        description="Solde et statut du wallet de l'utilisateur.",
        responses=WalletSerializer
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_object(self):
        return WalletService.get_wallet(self.request.user)

    serializer_class = WalletSerializer


class WalletTransactionsView(ListAPIView):
    """GET /api/v1/payments/wallet/transactions/ - Historique des transactions."""

    permission_classes = [IsAuthenticated]
    serializer_class = WalletTransactionSerializer

    @extend_schema(
        summary="Historique des transactions Wallet",
        description="Historique des transactions du wallet de l'utilisateur.",
        responses=WalletTransactionSerializer(many=True)
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        wallet = WalletService.get_wallet(self.request.user)
        return wallet.transactions.select_related("order").order_by("-created_at")



class WalletDepositView(APIView):
    """POST /api/v1/payments/wallet/deposit/ - Initier une recharge de wallet via PayDunya."""

    permission_classes = [IsAuthenticated, IsCustomer | IsPlatformAdmin]

    @extend_schema(
        summary="Recharger le Wallet",
        description="Initier une recharge de wallet via PayDunya.",
        request=DepositSerializer,
        responses={
            201: inline_serializer(
                name="WalletDepositResponse",
                fields={
                    "payment_id": serializers.IntegerField(),
                    "redirect_url": serializers.URLField(),
                    "token": serializers.CharField(),
                }
            ),
            400: OpenApiResponse(description="Wallet inactif"),
            502: OpenApiResponse(description="Erreur de la passerelle de paiement")
        }
    )
    def post(self, request):
        serializer = DepositSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        payment_service = PaymentService()
        try:
            payment, redirect_url = payment_service.initiate_wallet_topup(
                user=request.user,
                amount=serializer.validated_data["amount"],
                phone_number=serializer.validated_data["phone_number"],
            )
            return Response(
                {
                    "payment_id": payment.id,
                    "redirect_url": redirect_url,
                    "token": payment.reference_externe,
                },
                status=status.HTTP_201_CREATED,
            )
        except WalletInactiveError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except PaymentGatewayError as e:
            return Response({"detail": str(e)}, status=status.HTTP_502_BAD_GATEWAY)






class WalletPayView(APIView):
    """POST /api/v1/payments/wallet/achat/ - Payer une commande avec le wallet."""

    permission_classes = [IsAuthenticated, IsCustomer | IsPlatformAdmin]

    @extend_schema(
        summary="Payer avec le Wallet",
        description="Payer une commande avec le solde du wallet.",
        request=WalletPaySerializer,
        responses={
            200: PaymentSerializer,
            402: OpenApiResponse(description="Solde insuffisant"),
            400: OpenApiResponse(description="Wallet inactif ou autre erreur de validation")
        }
    )

    def post(self, request):
        serializer = WalletPaySerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)

        order_id = serializer.validated_data["order_id"]
        from apps.commandes.models import Order

        order = Order.objects.get(pk=order_id)
        payment_service = PaymentService()
        try:
            payment = payment_service.process_wallet_payment(
                user=request.user, order=order
            )
            return Response(
                PaymentSerializer(payment).data,
                status=status.HTTP_200_OK,
            )
        except InsufficientBalanceError as e:
            return Response({"detail": str(e)}, status=status.HTTP_402_PAYMENT_REQUIRED)
        except WalletInactiveError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)





class PaymentInitiateView(APIView):
    """POST /api/v1/payments/initiate/ - Paiement direct PayDunya (authentifié ou non)."""

    permission_classes = []  # AllowAny pour les visiteurs anonymes

    @extend_schema(
        summary="Initier un paiement PayDunya",
        description="Paiement direct PayDunya (authentifié ou non).",
        request=InitiatePaymentSerializer,
        responses={
            201: inline_serializer(
                name="InitiatePaymentResponse",
                fields={
                    "payment_id": serializers.IntegerField(),
                    "redirect_url": serializers.URLField(),
                    "token": serializers.CharField(),
                }
            ),
            502: OpenApiResponse(description="Erreur de la passerelle de paiement")
        }
    )
    def post(self, request):
        logger.info(f"[PaymentInitiateView] Requête POST reçue avec payload: {request.data}")
        serializer = InitiatePaymentSerializer(data=request.data, context={"request": request})
        try:
            serializer.is_valid(raise_exception=True)
            logger.info(f"[PaymentInitiateView] Serializer valide. Données validées: {serializer.validated_data}")
        except Exception as e:
            logger.error(f"[PaymentInitiateView] Erreur de validation du serializer: {e}")
            raise

        payment_service = PaymentService()
        data = serializer.validated_data
        order = None
        if data.get("order_id"):
            from apps.commandes.models import Order
            try:
                order = Order.objects.get(pk=data["order_id"])
                logger.info(f"[PaymentInitiateView] Commande trouvée: {order.reference}")
            except Order.DoesNotExist:
                logger.error(f"[PaymentInitiateView] Commande avec pk={data['order_id']} introuvable.")
                # Laisse l'erreur se propager ou gère la
                raise
                
        try:
            logger.info(f"[PaymentInitiateView] Appel de payment_service.initiate_direct_payment...")
            payment, redirect_url = payment_service.initiate_direct_payment(
                order=order,
                phone_number=data["phone_number"],
                user=request.user if request.user.is_authenticated else None,
            )
            logger.info(f"[PaymentInitiateView] Succès. payment_id={payment.id}, url={redirect_url}")
            return Response(
                {
                    "payment_id": payment.id,
                    "redirect_url": redirect_url,
                    "token": payment.reference_externe,
                },
                status=status.HTTP_201_CREATED,
            )
        except PaymentGatewayError as e:
            logger.error(f"[PaymentInitiateView] Erreur PaymentGatewayError interceptée: {e}")
            return Response({"detail": str(e)}, status=status.HTTP_502_BAD_GATEWAY)
        except Exception as e:
            logger.exception(f"[PaymentInitiateView] Erreur inattendue: {e}")
            raise



class PayDunyaWebhookView(APIView):
    """POST /api/v1/payments/webhook/paydunya/ - Callback PayDunya (public)."""

    permission_classes = [AllowAny]

    @extend_schema(
        summary="Webhook PayDunya",
        description="Callback PayDunya (public) pour confirmer un paiement reponse directe de payDunya.",
        request=inline_serializer(
            name="WebhookPayload",
            fields={
                "token": serializers.CharField(help_text="Token PayDunya du paiement")
            }
        ),
        responses={
            200: PaymentSerializer,
            400: OpenApiResponse(description="Token manquant"),
            502: OpenApiResponse(description="Erreur de la passerelle de paiement"),
            500: OpenApiResponse(description="Erreur interne du webhook")
        }
    )
    def post(self, request):
        token = request.data.get("token")
        if not token:
            return Response(
                {"detail": "Token manquant."}, status=status.HTTP_400_BAD_REQUEST
            )
        payment_service = PaymentService()
        try:
            payment = payment_service.handle_webhook(token, request.data)
            return Response(
                PaymentSerializer(payment).data,
                status=status.HTTP_200_OK,
            )
        except PaymentGatewayError as e:
            return Response({"detail": str(e)}, status=status.HTTP_502_BAD_GATEWAY)
        except Exception as e:
            return Response(
                {"detail": "Erreur interne du webhook."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class AdminWithdrawView(APIView):
    """POST /api/v1/payments/admin/retrait-fonds/ - Retrait de fonds vers un numéro mobile money (admin)."""

    permission_classes = [IsPlatformAdmin]

    @extend_schema(
        summary="Retrait Admin (Mobile Money)",
        description="Retrait de fonds vers un numéro mobile money par l'administrateur.",
        request=AdminWithdrawSerializer,
        responses={
            200: PaymentSerializer,
            502: OpenApiResponse(description="Erreur de la passerelle de paiement")
        }
    )
    def post(self, request):
        serializer = AdminWithdrawSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        payment_service = PaymentService()
        try:
            payment = payment_service.admin_withdraw(
                amount=serializer.validated_data["amount"],
                phone_number=serializer.validated_data["phone_number"],
                description=serializer.validated_data.get("description", ""),
            )
            return Response(
                PaymentSerializer(payment).data,
                status=status.HTTP_200_OK,
            )
        except PaymentGatewayError as e:
            return Response({"detail": str(e)}, status=status.HTTP_502_BAD_GATEWAY)



class OrderRefundView(APIView):
    """POST /api/v1/payments/refund/ - Demande manuelle de remboursement d'une commande (Admin ou client autorisé)."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Demander un remboursement",
        description="Demande manuelle de remboursement d'une commande (Admin ou client autorisé).",
        request=OrderRefundSerializer,
        responses={
            200: inline_serializer(
                name="OrderRefundResponse",
                fields={
                    "detail": serializers.CharField(),
                    "refunded_payments": PaymentSerializer(many=True),
                }
            ),
            403: OpenApiResponse(description="Non autorisé à rembourser"),
            404: OpenApiResponse(description="Aucun paiement trouvé"),
            500: OpenApiResponse(description="Erreur lors du remboursement")
        }
    )
    def post(self, request):
        from .serializers import OrderRefundSerializer
        serializer = OrderRefundSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        order_id = serializer.validated_data["order_id"]
        from apps.commandes.models import Order
        order = Order.objects.get(pk=order_id)

        # Vérifier les permissions (soit admin, soit le client lui-même)
        if not request.user.is_staff and order.user != request.user:
            return Response(
                {"detail": "Vous n'êtes pas autorisé à rembourser cette commande."},
                status=status.HTTP_403_FORBIDDEN
            )

        payment_service = PaymentService()
        try:
            refunded_payments = payment_service.refund_order(order, description="Remboursement manuel via API")
            if not refunded_payments:
                return Response(
                    {"detail": "Aucun paiement réussi trouvé pour cette commande."},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            return Response(
                {
                    "detail": f"{len(refunded_payments)} paiement(s) remboursé(s) avec succès.",
                    "refunded_payments": PaymentSerializer(refunded_payments, many=True).data
                },
                status=status.HTTP_200_OK
            )
        except Exception as e:
            return Response(
                {"detail": f"Erreur lors du remboursement : {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )




class AdminAllTransactionsView(ListAPIView):
    """
    GET /api/v1/paiements/admin/all-transactions/

    Retourne l'historique complet et unifié de toutes les transactions
    financières de l'utilisateur connecté :
      - Paiements de commandes (via Wallet ou PayDunya)
      - Recharges de portefeuille
      - Remboursements reçus

    Idéal pour afficher un relevé de compte sur le dashboard client.
    """
    permission_classes = [IsPlatformAdmin]

    def get_serializer_class(self):
        from .serializers import MyTransferSerializer
        return MyTransferSerializer

    @extend_schema(
        summary="Mes transferts (Historique global)",
        description="Retourne l'historique complet et unifié de toutes les transactions financières (Wallet, PayDunya, Remboursements).",
        responses=MyTransferSerializer(many=True) # type: ignore
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        from .models import GlobalTransaction
        return (
            GlobalTransaction.objects
            .select_related("order", "user")
            .order_by("-created_at")
        )


class AdminWalletListView(ListAPIView):
    """
    GET /api/v1/paiements/admin/wallets/
    Liste tous les wallets avec leur solde et renvoie le solde total cumulé de la plateforme.
    """
    permission_classes = [IsPlatformAdmin]
    serializer_class = AdminWalletSerializer
    
    def get_queryset(self):
        return Wallet.objects.select_related('user').all().order_by('-created_at')

    @extend_schema(
        summary="Liste des wallets (Admin)",
        description="Liste tous les wallets des clients avec le solde total cumulé en métadonnées.",
        responses={
            200: inline_serializer(
                name="AdminWalletListResponse",
                fields={
                    "total_platform_balance": serializers.DecimalField(max_digits=15, decimal_places=2),
                    "count": serializers.IntegerField(),
                    "next": serializers.URLField(allow_null=True),
                    "previous": serializers.URLField(allow_null=True),
                    "results": AdminWalletSerializer(many=True)
                }
            )
        }
    )
    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        
        # Calcul du solde total
        total_balance = queryset.aggregate(total=Sum('balance'))['total'] or Decimal('0.00')
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            response = self.get_paginated_response(serializer.data)
            # Ajout du solde total à la réponse paginée
            response.data['total_platform_balance'] = total_balance
            return response

        serializer = self.get_serializer(queryset, many=True)
        return Response({
            'total_platform_balance': total_balance,
            'results': serializer.data
        })


class AdminWalletStatusUpdateView(APIView):
    """
    PATCH /api/v1/paiements/admin/wallets/<uuid:pk>/status/
    Permet à l'admin de désactiver (suspendre/bloquer) ou réactiver un wallet.
    Interdit si le solde est > 0.
    """
    permission_classes = [IsPlatformAdmin]

    @extend_schema(
        summary="Modifier le statut d'un wallet (Admin)",
        description="Désactive ou clôture un compte uniquement en cas de force majeure et si le solde est nul.",
        request=AdminWalletStatusUpdateSerializer,
        responses={
            200: AdminWalletSerializer,
            400: OpenApiResponse(description="Modification interdite car solde > 0, ou données invalides."),
            404: OpenApiResponse(description="Wallet introuvable.")
        }
    )
    def patch(self, request, pk):
        from django.shortcuts import get_object_or_404
        wallet = get_object_or_404(Wallet, pk=pk)
        
        serializer = AdminWalletStatusUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        new_status = serializer.validated_data['status']
        
        # Règle stricte: aucun changement si solde > 0
        if wallet.balance > Decimal('0.00'):
            return Response(
                {
                    "detail": "Action impossible. Ce wallet a un solde positif. L'utilisateur doit être remboursé ou vider son compte avant toute modification de statut."
                },
                status=status.HTTP_400_BAD_REQUEST
            )
            
        wallet.status = new_status
        wallet.save()
        
        return Response(AdminWalletSerializer(wallet).data, status=status.HTTP_200_OK)