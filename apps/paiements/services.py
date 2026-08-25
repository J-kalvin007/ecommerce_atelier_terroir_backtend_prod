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
            # `reference_externe` porte à lui seul l'idempotence : il est
            # l'unique clé de rapprochement avec le token PayDunya. L'ancien
            # champ `webhook_token` n'existe pas sur le modèle Payment (il est
            # commenté dans models.py) : l'affecter faisait échouer le save()
            # avec « The following fields do not exist in this model », ce qui
            # cassait POST /paiements/wallet/deposit/ en production.
            payment.reference_externe = response["token"]
            payment.save(update_fields=["reference_externe", "updated_at"])
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
            payment.save(update_fields=["reference_externe", "updated_at"])
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
                payment.save(update_fields=["status", "reference_externe", "updated_at"])
                OrderService.update_status(
                    order=order,
                    new_status=OrderStatus.PAID,
                    changed_by=user,
                    comment="Paiement validé par Wallet"
                )

                # Le stock N'EST PAS décrémenté ici : OrderService.create_order
                # est le point unique de réservation du stock, appliqué dès la
                # création de la commande. Le re-décrémenter à l'encaissement
                # consommait deux fois le stock de chaque commande payée.

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

        - Applique l'idempotence basée sur le token (`reference_externe`).
        - Vérifie le statut auprès de l'API PayDunya : le corps du callback
          n'est JAMAIS considéré comme source de vérité.
        - Si succès et wallet_topup, crédite le wallet.

        Args:
            token: token PayDunya de la transaction.
            payload: corps brut du callback, conservé pour traçabilité.

        Returns:
            Payment: la ligne de paiement dans son état final.

        Raises:
            PaymentGatewayError: si la vérification auprès de PayDunya échoue.
        """
        logger.info("[PaymentService] Callback PayDunya reçu pour le token %s.", token)

        # ── Idempotence : `reference_externe` est l'unique clé de rapprochement
        # avec PayDunya. L'ancienne implémentation interrogeait un champ
        # `webhook_token` inexistant sur le modèle et journalisait dans un
        # `log_entry` jamais défini : toute exécution levait NameError.
        existing_payment = Payment.objects.filter(reference_externe=token).first()
        if existing_payment and existing_payment.status == Payment.Status.SUCCESS:
            logger.info(
                "[PaymentService] Token %s déjà traité avec succès : callback ignoré.",
                token,
            )
            return existing_payment

        # ── Vérification active auprès de PayDunya (source de vérité) ────────
        try:
            status_info = self.gateway.verify_payment(token)
        except PaymentGatewayError as e:
            logger.error(
                "[PaymentService] Échec de vérification du token %s : %s", token, e,
            )
            raise

        with transaction.atomic():
            if existing_payment:
                # Verrou pessimiste : sérialise deux callbacks concurrents.
                existing_payment = Payment.objects.select_for_update().get(
                    pk=existing_payment.pk,
                )
            else:
                # Cas rare : callback reçu avant la création du Payment local.
                existing_payment = Payment.objects.create(
                    provider=Payment.Provider.PAYDUNYA,
                    payment_type=Payment.PaymentType.WALLET_TOPUP,
                    amount=Decimal(str(status_info.get("amount") or "0")),
                    status=Payment.Status.PENDING,
                    reference_externe=token,
                )

            # Seconde barrière d'idempotence, à l'intérieur du verrou.
            if existing_payment.status == Payment.Status.SUCCESS:
                logger.info(
                    "[PaymentService] Token %s déjà au statut SUCCESS : callback ignoré.",
                    token,
                )
                return existing_payment

            if status_info.get("status") != "completed":
                existing_payment.status = Payment.Status.FAILED
                existing_payment.metadata = {
                    **(existing_payment.metadata or {}),
                    "webhook_payload": payload,
                    "verified_status": status_info.get("status"),
                }
                existing_payment.save(
                    update_fields=["status", "metadata", "updated_at"],
                )
                logger.warning(
                    "[PaymentService] Statut vérifié non finalisé pour %s : %s.",
                    token,
                    status_info.get("status"),
                )
                return existing_payment

            existing_payment.status = Payment.Status.SUCCESS
            existing_payment.metadata = {
                **(existing_payment.metadata or {}),
                "webhook_payload": payload,
                "verified_status": status_info.get("status"),
            }
            existing_payment.save(update_fields=["status", "metadata", "updated_at"])

            # Crédit wallet si nécessaire
            if existing_payment.payment_type == Payment.PaymentType.WALLET_TOPUP:
                # Le wallet est rattaché soit directement au paiement, soit à
                # l'utilisateur porteur de la transaction.
                wallet = existing_payment.wallet
                if wallet is None and existing_payment.user_id:
                    wallet = Wallet.objects.filter(
                        user_id=existing_payment.user_id,
                    ).first()

                if not wallet:
                    # Fallback : impossible sans lien, on log
                    logger.warning("Impossible de créditer : aucun wallet trouvé pour %s", token)
                else:
                    self.wallet_service.credit(
                        wallet=wallet,
                        amount=existing_payment.amount,
                        reference=f"WAL-{existing_payment.pk}",
                        metadata={"paydunya_token": token},
                    )

            elif existing_payment.payment_type == Payment.PaymentType.DIRECT_PAYMENT:
                # Mettre à jour la commande
                if existing_payment.order and existing_payment.order.status != OrderStatus.PAID:
                    OrderService.update_status(
                        order=existing_payment.order,
                        new_status=OrderStatus.PAID,
                        changed_by=None,
                        comment="Paiement validé par PayDunya (Webhook)"
                    )

            logger.info("[PaymentService] Token %s traité avec succès.", token)
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
                    metadata={"original_payment_id": str(payment.id), "reason": description},
                    transaction_type=WalletTransaction.Type.REFUND
                )
                refunded_payments.append(payment)

                logger.info(
                    "Paiement %s remboursé sur le wallet de %s",
                    payment.id,
                    user.email,
                )

        return refunded_payments
