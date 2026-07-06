import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from .models import Delivery, DeliveryStatus
from apps.commandes.models import OrderStatus

logger = logging.getLogger(__name__)

@receiver(post_save, sender=Delivery)
def update_order_status_on_delivery(sender, instance, created, **kwargs):
    """
    Met à jour automatiquement le statut de la commande associée 
    lorsque la livraison est marquée comme LIVRÉE (DELIVERED).
    """
    if instance.status == DeliveryStatus.DELIVERED:
        order = instance.order
        if order and order.status != OrderStatus.DELIVERED:
            order.status = OrderStatus.DELIVERED
            order.save(update_fields=["status", "updated_at"])
            logger.info(f"Signal déclenché : Commande {order.reference} mise à jour en DELIVERED via Livraison {instance.id}.")
