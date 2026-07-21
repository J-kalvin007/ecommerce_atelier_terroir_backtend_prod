from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db.models import F

from apps.commandes.models import OrderItem

@receiver(post_save, sender=OrderItem)
def increment_product_order_count(sender, instance, created, **kwargs):
    """
    Incrémente le nombre de commandes (order_count) d'un produit 
    lorsqu'une nouvelle ligne de commande (OrderItem) le contenant est créée.
    """
    if created and instance.product:
        # Utilisation de F() pour éviter les conditions de concurrence (race conditions)
        instance.product.order_count = F('order_count') + 1
        instance.product.save(update_fields=['order_count'])

from apps.commandes.models import OrderStatusHistory
from apps.commandes.services import FactureEmailService
from django.db import transaction

@receiver(post_save, sender=OrderStatusHistory)
def trigger_invoice_email_on_paid(sender, instance, created, **kwargs):
    """
    Déclenche l'envoi de l'email de facture lorsque le statut de la commande
    passe à "paid".
    """
    if created and instance.new_status == 'paid':
        # transaction.on_commit garantit que l'email n'est envoyé que si la transaction
        # en base de données a été validée avec succès.
        transaction.on_commit(lambda: FactureEmailService.send_invoice_email(instance.order))

@receiver(post_save, sender=OrderStatusHistory)
def trigger_delivery_creation_on_paid(sender, instance, created, **kwargs):
    """
    Crée automatiquement une livraison lorsque le statut de la commande
    passe à 'paid' et que la commande est marquée pour livraison.
    """
    if created and instance.new_status == 'paid':
        order = instance.order
        if order.is_for_delivery:
            from apps.livraisons.models import Delivery, DeliveryStatus
            
            def create_delivery():
                Delivery.objects.get_or_create(
                    order=order,
                    defaults={
                        'status': DeliveryStatus.PENDING,
                        'delivery_address': order.address_livraison,
                        'notes': order.notes
                    }
                )
                
            transaction.on_commit(create_delivery)
