"""
Couche de services métier pour les paiements et le portefeuille.

Utilise des transactions atomiques explicites et select_for_update()
pour garantir l'intégrité des soldes.
"""
import logging
from decimal import Decimal
from typing import Optional, Tuple

from django.db import transaction
from django.db.models import F
from django.utils import timezone

from apps.commandes.models import Order, OrderStatus
from apps.commandes.services import OrderService
from .exceptions import (
    InsufficientBalanceError,
    WalletInactiveError,
    PaymentAlreadyProcessedError,
    PaymentGatewayError,
)
from .gateways.paydunya import PayDunyaGateway
from .models import Wallet, WalletTransaction, Payment


logger = logging.getLogger(__name__)


class WalletService:
    """
    Gère les opérations sur le Wallet : consultation, crédit, débit.

    Toutes les modifications du solde sont encapsulées dans des transactions
    atomiques avec verrouillage pessimiste du wallet.
    """

    @staticmethod
    def get_balance(user) -> Decimal:
        """Retourne le solde du wallet de l'utilisateur (ou 0 s'il n'existe pas)."""
        wallet = Wallet.objects.filter(user=user).first()
        return wallet.balance if wallet else Decimal("0.00")

    @staticmethod
    def get_wallet(user) -> Wallet:
        """Récupère le wallet de l'utilisateur ou lève une exception s'il est inactif."""
        try:
            wallet = Wallet.objects.get(user=user)
        except Wallet.DoesNotExist:
            raise WalletInactiveError("Aucun portefeuille trouvé pour cet utilisateur.")
        if wallet.status != Wallet.Status.ACTIVE:
            raise WalletInactiveError(
                f"Le portefeuille est {wallet.get_status_display().lower()}."
            )
        return wallet


    @classmethod
    @transaction.atomic
    def credit(
        cls,
        wallet: Wallet,
        amount: Decimal,
        reference: str,
        metadata: dict = None,
        transaction_type: str = WalletTransaction.Type.DEPOSIT,
    ) -> WalletTransaction:
        """
        Crédite un wallet de manière atomique.

        Args:
            wallet: l'instance du portefeuille.
            amount: montant positif.
            reference: identifiant unique de la transaction.
            metadata: données supplémentaires.

        Returns:
            WalletTransaction créée.

        Raises:
            ValueError: si amount <= 0.
        """
        amount = amount.quantize(Decimal("0.01"))
        if amount <= 0:
            raise ValueError("Le montant doit être strictement positif.")

        # Verrouillage pessimiste
        locked_wallet = Wallet.objects.select_for_update().get(pk=wallet.pk)

        if locked_wallet.status != Wallet.Status.ACTIVE:
            raise WalletInactiveError("Impossible de créditer un portefeuille inactif.")

        locked_wallet.balance = F("balance") + amount
        locked_wallet.save(update_fields=["balance", "updated_at"])

        transaction_record = WalletTransaction.objects.create(
            wallet=locked_wallet,
            transaction_type=transaction_type,
            amount=amount,
            reference=reference,
            status=WalletTransaction.Status.SUCCESS,
            metadata=metadata or {},
        )

        # Recharger depuis la base pour obtenir la valeur réelle
        locked_wallet.refresh_from_db()
        logger.info(
            "Wallet %s crédité de %s, nouveau solde : %s",
            locked_wallet.user.email,
            amount,
            locked_wallet.balance,
        )
        return transaction_record



    @classmethod
    @transaction.atomic
    def debit(
        cls,
        wallet: Wallet,
        amount: Decimal,
        reference: str,
        order: Optional[Order] = None,
        metadata: dict = None,
    ) -> WalletTransaction:
        """
        Débite un wallet pour un paiement.

        Args:
            wallet: le portefeuille à débiter.
            amount: montant à retirer.
            reference: identifiant unique.
            order: commande liée (optionnelle).
            metadata: données additionnelles.

        Returns:
            WalletTransaction créée.

        Raises:
            InsufficientBalanceError: si le solde est insuffisant.
            WalletInactiveError: si le wallet n'est pas actif.
        """
        amount = amount.quantize(Decimal("0.01"))
        if amount < 0:
            raise ValueError("Le montant doit être positif ou nul.")

        locked_wallet = Wallet.objects.select_for_update().get(pk=wallet.pk)

        if locked_wallet.status != Wallet.Status.ACTIVE:
            raise WalletInactiveError("Paiement refusé, portefeuille inactif.")

        if locked_wallet.balance < amount:
            raise InsufficientBalanceError(
                f"Solde insuffisant ({locked_wallet.balance} FCFA) "
                f"pour un paiement de {amount} FCFA."
            )

        locked_wallet.balance = F("balance") - amount
        locked_wallet.save(update_fields=["balance", "updated_at"])

        transaction_record = WalletTransaction.objects.create(
            wallet=locked_wallet,
            transaction_type=WalletTransaction.Type.PAYMENT,
            amount=amount,
            reference=reference,
            order=order,
            status=WalletTransaction.Status.SUCCESS,
            metadata=metadata or {},
        )

        locked_wallet.refresh_from_db()
        logger.info(
            "Wallet %s débité de %s, nouveau solde : %s",
            locked_wallet.user.email,
            amount,
            locked_wallet.balance,
        )
        return transaction_record




class PaymentService:
    """
    Orchestrateur des flux de paiement.

    Coordonne la gateway PayDunya, le service Wallet et la persistance
    des transactions avec idempotence des webhooks.
    """

    def __init__(self):
        self.gateway = PayDunyaGateway()
        self.wallet_service = WalletService()

    def initiate_wallet_topup(
        self, user, amount: Decimal, phone_number: str
    ) -> Tuple[Payment, str]:
        """
        Démarre une recharge de wallet via PayDunya.

        Returns:
            (Payment, redirect_url) : l'objet Payment en attente et l'URL de paiement.
        """
        wallet = self.wallet_service.get_wallet(user)
        amount = amount.quantize(Decimal("0.01"))

        payment = Payment.objects.create(
            order=None,
            user=user,
            provider=Payment.Provider.PAYDUNYA,
            payment_type=Payment.PaymentType.WALLET_TOPUP,
            amount=amount,
            status=Payment.Status.PENDING,
        )

        # Appeler la gateway
        try:
            response = self.gateway.initiate_payment(
                amount=amount,
                phone_number=phone_number,
                description=f"Recharge wallet {user.email}",
                reference=payment.reference_externe,  # sera généré par la gateway
            )
            payment.reference_externe = response["token"]
            payment.webhook_token = response["token"]  # pour idempotence
            payment.save(update_fields=["reference_externe", "webhook_token"])
            return payment, response["redirect_url"]
        except PaymentGatewayError:
            payment.status = Payment.Status.FAILED
            payment.save(update_fields=["status"])
            raise






    def initiate_direct_payment(
        self, order: Order, phone_number: str, user=None
    ) -> Tuple[Payment, str]:
        """
        Paiement direct d'une commande via PayDunya (sans utilisation du wallet).
        """
        amount = order.total_final.quantize(Decimal("0.01"))

        payment = Payment.objects.create(
            order=order,
            user=user or (order.user if order else None),
            provider=Payment.Provider.PAYDUNYA,
            payment_type=Payment.PaymentType.DIRECT_PAYMENT,
            amount=amount,
            status=Payment.Status.PENDING,
        )

        logger.info(f"[PaymentService] initiate_direct_payment pour order {order.reference}, amount {amount}, phone {phone_number}")
        try:
            response = self.gateway.initiate_payment(
                amount=amount,
                phone_number=phone_number,
                description=f"Commande {order.reference}",
                reference=None,
            )
            logger.info(f"[PaymentService] Réponse gateway succès: {response}")
            payment.reference_externe = response["token"]
            payment.webhook_token = response["token"]
            payment.save(update_fields=["reference_externe", "webhook_token"])
            logger.info(f"[PaymentService] Payment model {payment.id} mis à jour.")
            return payment, response["redirect_url"]
        except PaymentGatewayError as e:
            logger.error(f"[PaymentService] PaymentGatewayError dans initiate_direct_payment: {e}")
            payment.status = Payment.Status.FAILED
            payment.save(update_fields=["status"])
            raise







    def process_wallet_payment(self, user, order: Order) -> Payment:
        """
        Paiement d'une commande via le wallet interne.

        Débite immédiatement le solde.
        """
        wallet = self.wallet_service.get_wallet(user)
        amount = order.total_final.quantize(Decimal("0.01"))

        with transaction.atomic():
            payment = Payment.objects.create(
                order=order,
                user=user,
                provider=Payment.Provider.WALLET,  
                payment_type=Payment.PaymentType.ORDER_PAYMENT,
                amount=amount,
                status=Payment.Status.PENDING,
            )
            reference = f"WAL-{payment.pk}"

            try:
                tx = self.wallet_service.debit(
                    wallet=wallet,
                    amount=amount,
                    reference=reference,
                    order=order,
                )
                payment.status = Payment.Status.SUCCESS
                payment.reference_externe = reference
                payment.save(update_fields=["status", "reference_externe"])
                OrderService.update_status(
                    order=order,
                    new_status=OrderStatus.PAID,
                    changed_by=user,
                    comment="Paiement validé par Wallet"
                )

                # --- Décrémentation des stocks ---
                from apps.catalog.models import ProductVariant
                for item in order.items.all():
                    # 1. Chercher si la ligne correspond à une variation via le SKU
                    variant = ProductVariant.objects.filter(sku=item.product_sku).first()
                    
                    if variant:
                        ancien_stock = variant.stock
                        variant.stock = max(0, variant.stock - item.quantity)
                        variant.save()
                        logger.info(f"Stock de la variante '{variant.name}' (SKU: {variant.sku}) décrémenté : {ancien_stock} -> {variant.stock}")
                        
                        produit_principal = variant.product
                        if produit_principal:
                            ancien_stock_p = produit_principal.stock
                            produit_principal.stock = max(0, produit_principal.stock - item.quantity)
                            produit_principal.save()
                            logger.info(f"Stock du produit '{produit_principal.name}' (SKU: {produit_principal.sku}) décrémenté : {ancien_stock_p} -> {produit_principal.stock}")
                    else:
                        # 2. Si aucune variation ne correspond, on décrémente le produit principal
                        produit_principal = item.product
                        if produit_principal:
                            ancien_stock = produit_principal.stock
                            produit_principal.stock = max(0, produit_principal.stock - item.quantity)
                            produit_principal.save()
                            logger.info(f"Stock du produit '{produit_principal.name}' (SKU: {produit_principal.sku}) décrémenté : {ancien_stock} -> {produit_principal.stock}")
                        else:
                            logger.warning(f"Impossible de décrémenter le stock : aucun produit/variante trouvé pour le SKU {item.product_sku}")

                logger.info(
                    "Commande %s payée via wallet (user %s).",
                    order.reference,
                    user.email,
                )
                return payment
            except InsufficientBalanceError:
                payment.status = Payment.Status.FAILED
                payment.save(update_fields=["status"])
                raise





    def handle_webhook(self, token: str, payload: dict) -> Payment:
        """
        Traite un callback PayDunya.

        - Vérifie le statut auprès de l'API PayDunya.
        - Applique l'idempotence basée sur le token.
        - Si succès et wallet_topup, crédite le wallet.
        """

        # Vérifier si le token a déjà été traité (idempotence)
        existing_payment = Payment.objects.filter(webhook_token=token).first()
        if existing_payment and existing_payment.status == Payment.Status.SUCCESS:
            log_entry.status_traitement = "duplicate"
            log_entry.notes = "Transaction déjà traitée avec succès."
            log_entry.save()
            return existing_payment

        # Vérification active auprès de PayDunya
        try:
            status_info = self.gateway.verify_payment(token)
        except PaymentGatewayError as e:
            log_entry.status_traitement = "error"
            log_entry.notes = f"Échec vérification gateway : {e}"
            log_entry.save()
            raise

        with transaction.atomic():
            if not existing_payment:
                # Tenter de retrouver un paiement par token (au cas où)
                existing_payment = Payment.objects.filter(
                    webhook_token=token
                ).first()
                if not existing_payment:
                    # Cas rare : callback avant création du Payment local
                    # On crée un objet minimum à partir du payload
                    existing_payment = Payment.objects.create(
                        provider=Payment.Provider.PAYDUNYA,
                        payment_type=Payment.PaymentType.WALLET_TOPUP,
                        amount=Decimal(status_info.get("amount", 0)),
                        status=Payment.Status.PENDING,
                        reference_externe=token,
                        webhook_token=token,
                    )

            if existing_payment.status == Payment.Status.SUCCESS:
                log_entry.status_traitement = "duplicate"
                log_entry.notes = "Déjà succès."
                log_entry.save()
                return existing_payment

            if status_info.get("status") != "completed":
                existing_payment.status = Payment.Status.FAILED
                existing_payment.save(update_fields=["status"])
                log_entry.status_traitement = "processed"
                log_entry.notes = "Statut PayDunya non 'completed'."
                log_entry.save()
                return existing_payment

            existing_payment.status = Payment.Status.SUCCESS
            existing_payment.save(update_fields=["status"])

            # Crédit wallet si nécessaire
            if existing_payment.payment_type == Payment.PaymentType.WALLET_TOPUP:
                wallet = Wallet.objects.filter(
                    user=existing_payment.order.user
                ).first() if existing_payment.order else None
                if not wallet:
                    # Fallback : impossible sans lien, on log
                    logger.warning("Impossible de créditer : aucun wallet trouvé pour %s", token)
                else:
                    self.wallet_service.credit(
                        wallet=wallet,
                        amount=existing_payment.amount,
                        reference=f"WAL-{existing_payment.pk}",
                        metadata={"webhook_token": token},
                    )

            elif existing_payment.payment_type == Payment.PaymentType.DIRECT_PAYMENT:
                # Mettre à jour la commande
                if existing_payment.order:
                    OrderService.update_status(
                        order=existing_payment.order,
                        new_status=OrderStatus.PAID,
                        changed_by=None,
                        comment="Paiement validé par PayDunya (Webhook)"
                    )

            log_entry.status_traitement = "processed"
            log_entry.notes = "Traitement réussi."
            log_entry.save()
            return existing_payment





    def admin_withdraw(
        self, amount: Decimal, phone_number: str, description: str = ""
    ) -> Payment:
        """
        Retrait de fonds initié par l'administrateur vers un numéro mobile money.

        Note: actuellement implémenté via la gateway PayDunya (payout).
        """
        amount = amount.quantize(Decimal("0.01"))
        payment = Payment.objects.create(
            user=None, # Admin operation
            provider=Payment.Provider.PAYDUNYA,
            payment_type=Payment.PaymentType.ADMIN_WITHDRAW,
            amount=amount,
            status=Payment.Status.PENDING,
        )
        try:
            response = self.gateway.request_payout(
                amount=amount,
                phone_number=phone_number,
                description=description or "Retrait administrateur",
            )
            payment.reference_externe = response.get("token", "")
            payment.status = Payment.Status.SUCCESS
            payment.save(update_fields=["reference_externe", "status"])
            return payment
        except PaymentGatewayError:
            payment.status = Payment.Status.FAILED
            payment.save(update_fields=["status"])
            raise

    def refund_order(self, order: Order, description: str = "Remboursement suite à annulation") -> list[Payment]:
        """
        Rembourse automatiquement les paiements réussis d'une commande annulée
        vers le portefeuille (Wallet) de l'utilisateur.
        """
        refunded_payments = []
        payments = Payment.objects.filter(order=order, status=Payment.Status.SUCCESS)

        if not payments.exists():
            return refunded_payments

        user = order.user
        try:
            wallet = self.wallet_service.get_wallet(user)
        except WalletInactiveError:
            # Fallback: create or get wallet if it somehow doesn't exist
            wallet, _ = Wallet.objects.get_or_create(user=user)

        with transaction.atomic():
            for payment in payments:
                # Mettre à jour le statut du paiement
                payment.status = Payment.Status.REFUNDED
                payment.save(update_fields=["status"])

                # Créditer le wallet
                self.wallet_service.credit(
                    wallet=wallet,
                    amount=payment.amount,
                    reference=f"REF-{payment.pk}",
                    metadata={"original_payment_id": payment.id, "reason": description},
                    transaction_type=WalletTransaction.Type.REFUND
                )
                refunded_payments.append(payment)

                logger.info(
                    "Paiement %s remboursé sur le wallet de %s",
                    payment.id,
                    user.email,
                )

        return refunded_payments
