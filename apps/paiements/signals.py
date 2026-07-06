"""
Signaux métier pour le module de paiement.
"""
from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Wallet


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_wallet_on_user_creation(sender, instance, created, **kwargs):
    """
    Crée automatiquement un Wallet lors de la création d'un nouvel utilisateur.
    """
    if created and not hasattr(instance, "wallet"):
        Wallet.objects.create(user=instance)


from apps.commandes.models import OrderStatusHistory, OrderStatus
from .services import PaymentService
import logging

logger = logging.getLogger(__name__)

@receiver(post_save, sender=OrderStatusHistory)
def process_refund_on_order_cancel(sender, instance, created, **kwargs):
    """
    Déclenche automatiquement le remboursement des paiements si la commande
    est annulée.
    """
    if created and instance.new_status == OrderStatus.CANCELLED:
        try:
            service = PaymentService()
            refunds = service.refund_order(instance.order)
            if refunds:
                logger.info(f"Remboursement automatique réussi pour la commande {instance.order.reference} ({len(refunds)} paiements).")
        except Exception as e:
            logger.error(f"Échec du remboursement automatique pour {instance.order.reference} : {e}")

from .models import Payment
from django.utils import timezone

@receiver(post_save, sender=Payment)
def update_order_status_on_payment_success(sender, instance, created, **kwargs):
    """
    Signal spécial : dès qu'un paiement (PayDunya ou Wallet) passe au statut SUCCESS,
    on vérifie qu'il s'agit bien d'un paiement direct de commande (et non d'une recharge wallet).
    Si c'est le cas, on met à jour automatiquement la commande liée au statut 'PAID'.
    """
    if instance.status == Payment.Status.SUCCESS and instance.payment_type == Payment.PaymentType.DIRECT_PAYMENT:
        if instance.order and instance.order.status != OrderStatus.PAID:
            instance.order.status = OrderStatus.PAID
            instance.order.paid_at = timezone.now()
            instance.order.save(update_fields=["status", "paid_at"])
            logger.info(f"Signal déclenché : Commande {instance.order.reference} mise à jour en PAID via paiement {instance.id}.")