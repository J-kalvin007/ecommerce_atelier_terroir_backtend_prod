


"""
Serializers DRF avec validation métier pour les endpoints de paiement.
"""
from decimal import Decimal
from rest_framework import serializers

from apps.commandes.models import Order
from .models import Wallet, WalletTransaction, Payment
from .services import WalletService
from ecommerce_backend.users.api.serializers import UserSerializer


class WalletSerializer(serializers.ModelSerializer):
    """Affichage du solde et statut."""

    class Meta:
        model = Wallet
        fields = ("id", "balance", "status", "created_at", "updated_at")
        read_only_fields = fields


class WalletTransactionSerializer(serializers.ModelSerializer):
    """Historique des transactions."""

    class Meta:
        model = WalletTransaction
        fields = (
            "id",
            "transaction_type",
            "amount",
            "reference",
            "order",
            "status",
            "created_at",
        )
        read_only_fields = fields


class DepositSerializer(serializers.Serializer):
    """Initiation d'une recharge de wallet."""

    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("1.00"))
    phone_number = serializers.CharField(max_length=30)

    def validate_phone_number(self, value):
        if not value.startswith("+"):
            raise serializers.ValidationError("Le numéro doit être au format international (+221...).")
        return value


class WalletPaySerializer(serializers.Serializer):
    """Paiement d'une commande via le wallet."""

    order_id = serializers.UUIDField()

    def validate_order_id(self, value):
        try:
            order = Order.objects.get(pk=value)
        except Order.DoesNotExist:
            raise serializers.ValidationError("Commande introuvable.")
        if order.status not in ("pending_payment",):
            raise serializers.ValidationError("Cette commande ne peut plus être payée.")
        if order.user != self.context["request"].user:
            raise serializers.ValidationError("Vous ne pouvez payer que vos propres commandes.")
        return value


class InitiatePaymentSerializer(serializers.Serializer):
    """Paiement direct PayDunya (avec ou sans commande existante)."""

    order_id = serializers.UUIDField(required=False, allow_null=True)
    description = serializers.CharField(max_length=30)
    # Le montant envoyé par le client est informatif uniquement.
    # Le service utilise order.total_final comme source de vérité.
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("1.00"), required=False, allow_null=True)
    phone_number = serializers.CharField(max_length=30)

    def validate(self, data):
        if data.get("order_id"):
            try:
                order = Order.objects.get(pk=data["order_id"])
                if order.status not in ("pending_payment", "draft"):
                    raise serializers.ValidationError(
                        "Cette commande ne peut plus être payée (statut: {}).".format(order.status)
                    )
                if self.context.get("request") and self.context["request"].user.is_authenticated:
                    if order.user != self.context["request"].user:
                        raise serializers.ValidationError(
                            "Vous ne pouvez payer que vos propres commandes."
                        )
            except Order.DoesNotExist:
                raise serializers.ValidationError("Commande introuvable.")
        return data

    def validate_phone_number(self, value):
        if not value.startswith("+"):
            raise serializers.ValidationError("Format international requis (+221...).")
        return value







class PaymentSerializer(serializers.ModelSerializer):
    """Détail d'un paiement."""

    class Meta:
        model = Payment
        fields = (
            "id",
            "order",
            "provider",
            "payment_type",
            "amount",
            "status",
            "reference_externe",
            "created_at",
        )
        read_only_fields = fields


class AdminWithdrawSerializer(serializers.Serializer):
    """Demande de retrait administrateur."""

    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("1.00"))
    phone_number = serializers.CharField(max_length=30)
    description = serializers.CharField(max_length=255, required=False, allow_blank=True)


class OrderRefundSerializer(serializers.Serializer):
    """
    Serializer pour demander manuellement le remboursement d'une commande.
    """
    order_id = serializers.UUIDField()

    def validate_order_id(self, value):
        try:
            order = Order.objects.get(pk=value)
        except Order.DoesNotExist:
            raise serializers.ValidationError("Commande introuvable.")
        
        # On ne rembourse que si la commande est bien annulée
        if order.status != "cancelled":
            raise serializers.ValidationError("Seules les commandes annulées peuvent être remboursées manuellement.")
        return value


class MyTransferSerializer(serializers.ModelSerializer):
    """
    Sérialise toutes les transactions financières d'un utilisateur (Wallet + PayDunya)
    pour affichage sur le dashboard client.
    """
    type_label = serializers.SerializerMethodField()
    status_label = serializers.SerializerMethodField()
    order_reference = serializers.SerializerMethodField()
    provider_label = serializers.SerializerMethodField()
    client = UserSerializer(source='user', read_only=True)

    class Meta:
        model = Payment
        fields = (
            "id",
            "client",
            "type_label",
            "status_label",
            "provider_label",
            "amount",
            "reference_externe",
            "order",
            "order_reference",
            "created_at",
        )
        read_only_fields = fields

    def get_type_label(self, obj):
        LABELS = {
            "order_payment":  {"label": "Paiement commande",   "icon": "🛒"},
            "wallet_topup":   {"label": "Recharge portefeuille","icon": "💰"},
            "direct_payment": {"label": "Paiement direct",      "icon": "💳"},
            "admin_withdraw": {"label": "Retrait",              "icon": "🏦"},
        }
        data = LABELS.get(obj.payment_type, {"label": obj.get_payment_type_display(), "icon": "📄"})
        return data

    def get_status_label(self, obj):
        STATUS = {
            "pending":  {"label": "En attente",  "color": "#f57c00"},
            "success":  {"label": "Réussi",      "color": "#388e3c"},
            "failed":   {"label": "Échoué",      "color": "#d32f2f"},
            "refunded": {"label": "Remboursé",   "color": "#455a64"},
            "cancelled":{"label": "Annulé",      "color": "#9e9e9e"},
        }
        return STATUS.get(obj.status, {"label": obj.get_status_display(), "color": "#999"})

    def get_order_reference(self, obj):
        return obj.order.reference if obj.order else None

    def get_provider_label(self, obj):
        PROVIDERS = {
            "paydunya": {"label": "PayDunya",  "icon": "📱"},
            "stripe":   {"label": "Stripe",    "icon": "💳"},
            "wallet":   {"label": "Portefeuille interne", "icon": "👛"},
        }
        return PROVIDERS.get(obj.provider, {"label": obj.get_provider_display(), "icon": "🔄"})


class AdminWalletSerializer(serializers.ModelSerializer):
    """Affichage complet du wallet pour l'administration."""
    user_email = serializers.CharField(source='user.email', read_only=True)
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    client = UserSerializer(source='user', read_only=True)

    class Meta:
        model = Wallet
        fields = ("id", "client", "user_email", "user_name", "balance", "status", "created_at", "updated_at")
        read_only_fields = fields


class AdminWalletStatusUpdateSerializer(serializers.Serializer):
    """Mise à jour du statut d'un wallet par l'admin."""
    status = serializers.ChoiceField(choices=Wallet.Status.choices)
