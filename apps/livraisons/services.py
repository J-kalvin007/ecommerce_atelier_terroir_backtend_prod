from django.db import transaction
from decimal import Decimal
from .models import FraisLivraison, Delivery, DeliveryStatus
from apps.commandes.models import Order

class LivraisonService:
    @staticmethod
    def get_current_frais_livraison() -> Decimal:
        """Récupère le frais de livraison par km le plus récent."""
        frais = FraisLivraison.objects.filter(is_active=True).first()
        return frais.prix_livraison if frais else Decimal('0.00')

    @staticmethod
    def calculate_delivery_cost(distance_km: Decimal) -> Decimal:
        """Calcule le coût de la livraison en fonction de la distance en km."""
        prix_par_km = LivraisonService.get_current_frais_livraison()
        return prix_par_km * distance_km

    @staticmethod
    @transaction.atomic
    def create_delivery_for_order(order: Order, address: str = "") -> Delivery:
        """
        Crée une entité Delivery pour une commande donnée.
        """
        delivery, created = Delivery.objects.get_or_create(
            order=order,
            defaults={
                "delivery_address": address or order.address_livraison,
                "status": DeliveryStatus.PENDING
            }
        )
        return delivery


class DeliveryService:
    """
    Service métier pour la gestion du cycle de vie des livraisons.
    """

    @staticmethod
    @transaction.atomic
    def assign_livreur(delivery: Delivery, livreur: 'Livreur', user=None) -> Delivery:
        """
        Assigne un livreur à une livraison et passe le statut à ASSIGNED.
        Crée une entrée d'historique.
        """
        if delivery.status in [DeliveryStatus.DELIVERED, DeliveryStatus.CANCELLED]:
            raise ValueError("Impossible d'assigner un livreur à une livraison terminée ou annulée.")

        old_status = delivery.status
        delivery.livreur = livreur
        delivery.status = DeliveryStatus.ASSIGNED
        delivery.save(update_fields=["livreur", "status", "updated_at"])

        from .models import DeliveryStatusHistory
        DeliveryStatusHistory.objects.create(
            delivery=delivery,
            old_status=old_status,
            new_status=DeliveryStatus.ASSIGNED,
            changed_by=user,
            notes=f"Livreur {livreur.nom_complet} assigné."
        )

        return delivery

    @staticmethod
    @transaction.atomic
    def update_status(delivery: Delivery, new_status: str, user=None, notes: str = "") -> Delivery:
        """
        Met à jour le statut d'une livraison et trace le changement dans l'historique.
        """
        if delivery.status == new_status:
            return delivery

        if delivery.status in [DeliveryStatus.DELIVERED, DeliveryStatus.CANCELLED]:
            raise ValueError(f"La livraison est déjà dans un état terminal ({delivery.status}).")

        old_status = delivery.status
        delivery.status = new_status
        
        from django.utils import timezone
        if new_status == DeliveryStatus.DELIVERED:
            delivery.actual_delivery_date = timezone.now()
            delivery.save(update_fields=["status", "actual_delivery_date", "updated_at"])
        else:
            delivery.save(update_fields=["status", "updated_at"])

        from .models import DeliveryStatusHistory
        DeliveryStatusHistory.objects.create(
            delivery=delivery,
            old_status=old_status,
            new_status=new_status,
            changed_by=user,
            notes=notes
        )

        DeliveryService._sync_order_status(delivery, user)

        return delivery

    @staticmethod
    def _sync_order_status(delivery: Delivery, user=None):
        """
        Synchronise le statut de la livraison vers la commande associée.
        Appelé après un changement de statut de livraison.
        """
        from apps.commandes.services import OrderService
        from apps.commandes.models import OrderStatus

        order = delivery.order
        if not order:
            return

        new_order_status = None
        if delivery.status == DeliveryStatus.IN_TRANSIT:
            new_order_status = OrderStatus.SHIPPED
        elif delivery.status == DeliveryStatus.DELIVERED:
            new_order_status = OrderStatus.DELIVERED

        # On ne change pas le statut de la commande si la livraison est annulée
        # (doit être géré manuellement pour remboursement etc.)

        if new_order_status and order.status != new_order_status:
            # Sécurité : on ne rétrograde pas une commande déjà terminée/annulée
            if order.status in [OrderStatus.DELIVERED, OrderStatus.CANCELLED, OrderStatus.REFUNDED]:
                return

            OrderService.update_status(
                order=order,
                new_status=new_order_status,
                changed_by=user,
                comment=f"Synchronisation auto depuis livraison {delivery.id} ({delivery.status})"
            )


