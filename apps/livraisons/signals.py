import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from apps.commandes.models import Order, OrderStatus
from .models import Delivery
from .services import DeliveryService, LivraisonService

logger = logging.getLogger(__name__)

@receiver(post_save, sender=Order)
def ensure_delivery_for_order(sender, instance, created, **kwargs):
    """
    Couche filet (descendante) : s'assure qu'une livraison existe pour toute
    commande devant être livrée et ayant atteint un statut actif.
    """
    if not instance.is_for_delivery:
        return

    active_statuses = [
        OrderStatus.PAID,
        OrderStatus.CONFIRMED,
        OrderStatus.PROCESSING,
        OrderStatus.SHIPPED,
    ]

    if instance.status in active_statuses:
        # get_or_create s'assure qu'on ne crée pas de doublon
        delivery, delivery_created = Delivery.objects.get_or_create(
            order=instance,
            defaults={
                "delivery_address": instance.address_livraison,
            }
        )
        if delivery_created:
            logger.info(f"Livraison {delivery.id} auto-créée via signal pour la commande {instance.reference}.")


@receiver(post_save, sender=Delivery)
def sync_order_status_from_delivery(sender, instance, created, **kwargs):
    """
    Couche filet (montante) : si une livraison est modifiée hors du DeliveryService
    (ex: via l'Admin Django), on s'assure que le statut de la commande est synchronisé.
    La vraie logique de mise à jour est centralisée dans le service.
    """
    if not created:
        # Appel du service métier au lieu de modifier brutalement order.status
        DeliveryService._sync_order_status(instance, user=None)
