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
