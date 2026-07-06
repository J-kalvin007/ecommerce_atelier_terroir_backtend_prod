from django.db import models
from django.conf import settings
from apps.core.models import BaseModel
from apps.commandes.models import Order

class FraisLivraison(BaseModel):
    """
    Table pour gerer les frais de livraison par defaut pour 1Km dynamiquement par l'admin
    """
    prix_livraison = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    
    coordonnee_admin = models.CharField(
        max_length=255, 
        default="6.137482, 1.212820", 
        help_text="Coordonnées GPS (latitude, longitude) de l'admin. Par défaut: Lomé."
    )

    class Meta:
        db_table = "livraisons_frais"
        verbose_name = "Frais de livraison"
        verbose_name_plural = "Frais de livraison"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["prix_livraison"]),
            models.Index(fields=["-created_at"]),
        ]

    def __str__(self):
        return f"Prix par Km: {self.prix_livraison}"


class DeliveryStatus(models.TextChoices):
    PENDING = "pending", "En attente"
    IN_TRANSIT = "in_transit", "En transit"
    DELIVERED = "delivered", "Livrée"
    CANCELLED = "cancelled", "Annulée"


class Delivery(BaseModel):
    """
    Suivi d'une livraison individuelle pour une commande spécifique.
    """
    order = models.OneToOneField(
        Order,
        on_delete=models.CASCADE,
        related_name="delivery"
    )

    status = models.CharField(
        max_length=20,
        choices=DeliveryStatus.choices,
        default=DeliveryStatus.PENDING,
        db_index=True
    )

    delivery_address = models.TextField(blank=True)
    
    tracking_number = models.CharField(max_length=100, blank=True)
    
    delivery_person = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="deliveries_handled",
        help_text="L'utilisateur (livreur) en charge de cette livraison."
    )

    estimated_delivery_date = models.DateTimeField(null=True, blank=True)
    
    actual_delivery_date = models.DateTimeField(null=True, blank=True)

    notes = models.TextField(blank=True)

    class Meta:
        db_table = "livraisons_delivery"
        verbose_name = "Livraison"
        verbose_name_plural = "Livraisons"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "-created_at"]),
        ]

    def __str__(self):
        return f"Livraison {self.id} pour Cmd {self.order.reference}"
