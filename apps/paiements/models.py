"""
Modèles du module de paiement.

- Wallet : portefeuille électronique lié à l'utilisateur.
- WalletTransaction : historique de toutes les opérations sur le wallet.
- Payment : transaction de paiement, qu'elle passe par PayDunya ou le wallet.
- PayDunyaWebhookLog : journal brut des callbacks reçus.
"""
from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models, transaction

from apps.core.models import BaseModel


class Wallet(BaseModel):
    """
    Portefeuille personnel d'un utilisateur authentifié.

    Attributs :
        user (OneToOneField) : utilisateur propriétaire.
        balance (Decimal) : solde courant, ne peut être négatif.
        status (CharField) : actif, suspendu ou bloqué.
    """

    class Status(models.TextChoices):
        ACTIVE = "active", "Actif"
        SUSPENDED = "suspendu", "Suspendu"
        BLOCKED = "blocked", "Bloqué"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="wallet",
    )

    balance = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
        db_index=True,
    )


    reference = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        unique=True,
    )

    class Meta:
        db_table = "payments_wallets"
        verbose_name = "Portefeuille"
        verbose_name_plural = "Portefeuilles"
        indexes = [
            models.Index(fields=["user"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return f"Wallet de {self.user.email} ({self.balance} FCFA)"







class WalletTransaction(BaseModel):
    """
    Mouvement financier sur un Wallet.

    Chaque mouvement est lié à un Wallet obligatoirement et éventuellement à une commande.
    """

    class Type(models.TextChoices):
        DEPOSIT = "deposit", "Dépôt"
        WITHDRAWAL = "withdrawal", "Retrait"
        PAYMENT = "payment", "Paiement"
        REFUND = "refund", "Remboursement"
        CASHBACK = "cashback", "Cashback"

    class Status(models.TextChoices):
        PENDING = "pending", "En attente"
        SUCCESS = "success", "Réussi"
        FAILED = "failed", "Échoué"
        CANCELLED = "cancelled", "Annulé"

    wallet = models.ForeignKey(
        Wallet,
        on_delete=models.PROTECT,
        related_name="transactions",
    )

    transaction_type = models.CharField(
        max_length=20,
        choices=Type.choices,
        db_index=True,
    )

    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
    )

    reference = models.CharField(
        max_length=100,
        unique=True,
        db_index=True,
        help_text="Référence unique interne (UUID ou token).",
    )

    order = models.ForeignKey(
        "commandes.Order",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="wallet_transactions",
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )

    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Données additionnelles (token PayDunya, etc.)",
    )

    class Meta:
        db_table = "payments_wallet_transactions"
        verbose_name = "Transaction de portefeuille"
        verbose_name_plural = "Transactions de portefeuille"
        indexes = [
            # L'index sur "reference" est omis : unique=True l'implique déjà en DB.
            models.Index(fields=["wallet", "-created_at"]),
        ]


    def __str__(self):
        return f"{self.transaction_type} de {self.amount} ({self.status})"








class Payment(BaseModel):
    """
    Transaction de paiement (quel que soit le fournisseur).

    Peut être liée à une commande, ou rester orpheline pour les recharges de wallet.
    """

    class Provider(models.TextChoices):
        PAYDUNYA = "paydunya", "PayDunya"
        STRIPE = "stripe", "Stripe"
        # MOOV = "moov", "Moov Money"
        # TMONEY = "tmoney", "Tmoney"
        WALLET = "wallet", "Portefeuille interne"

    class PaymentType(models.TextChoices):
        ORDER_PAYMENT = "order_payment", "Paiement de commande"
        WALLET_TOPUP = "wallet_topup", "Recharge de portefeuille"
        DIRECT_PAYMENT = "direct_payment", "Paiement direct (sans compte)"
        ADMIN_WITHDRAW = "admin_withdraw", "Retrait administrateur"

    class Status(models.TextChoices):
        PENDING = "pending", "En attente"
        SUCCESS = "success", "Réussi"
        FAILED = "failed", "Échoué"
        CANCELLED = "cancelled", "Annulé"
        REFUNDED = "refunded", "Remboursé"

    order = models.ForeignKey(
        "commandes.Order",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payments",
        help_text="Commande associée (null pour les recharges wallet).",
    )

    wallet = models.ForeignKey(
        "Wallet",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="Portefeuille",
        help_text="Wallet associer (null pour les recharges wallet).",
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payments",
        help_text="Utilisateur lié à la transaction (pour traçabilité globale).",
    )

    provider = models.CharField(
        max_length=20,
        choices=Provider.choices,
        db_index=True,
    )

    payment_type = models.CharField(
        max_length=20,
        choices=PaymentType.choices,
        db_index=True,
    )

    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )

    reference_externe = models.CharField(
        max_length=100,
        blank=True,
        help_text="Token PayDunya ou autre référence externe.",
    )

    # webhook_token = models.CharField(
    #     max_length=100,
    #     unique=True,
    #     null=True,
    #     blank=True,
    #     help_text="Token utilisé dans le callback pour idempotence.",
    # )

    metadata = models.JSONField(
        default=dict,
        blank=True,
    )

    class Meta:
        db_table = "payments_payments"
        verbose_name = "Paiement"
        verbose_name_plural = "Paiements"
        indexes = [
            models.Index(fields=["order"]),
            models.Index(fields=["status", "-created_at"]),
            models.Index(fields=["reference_externe"]),
        ]

    def __str__(self):
        return f"{self.payment_type} via {self.provider} - {self.amount} ({self.status})"







# class PayDunyaWebhookLog(BaseModel):
#     """
#     Journal de chaque callback reçu de PayDunya.

#     Stocke le payload brut et le résultat du traitement pour audit.
#     """

#     token = models.CharField(
#         max_length=100,
#         db_index=True,
#         help_text="Token de la transaction PayDunya.",
#     )

#     payload = models.JSONField(
#         help_text="Payload JSON brut reçu.",
#     )

#     status_traitement = models.CharField(
#         max_length=20,
#         choices=(
#             ("processed", "Traité avec succès"),
#             ("duplicate", "Doublon ignoré"),
#             ("error", "Erreur lors du traitement"),
#         ),
#     )

#     notes = models.TextField(blank=True)

#     class Meta:
#         db_table = "payments_webhook_logs"
#         verbose_name = "Log webhook PayDunya"
#         verbose_name_plural = "Logs webhooks PayDunya"
#         indexes = [
#             models.Index(fields=["token"]),
#             models.Index(fields=["-created_at"]),
#         ]

#     def __str__(self):
#         return f"Webhook {self.token} - {self.status_traitement}"






class GlobalTransaction(Payment):
    """
    Proxy model pour afficher de manière unifiée toutes les transactions
    (Wallet, PayDunya, etc.) dans l'administration sous un nom dédié.
    """
    class Meta:
        proxy = True
        verbose_name = "Transaction Globale"
        verbose_name_plural = "Transactions Globales"









