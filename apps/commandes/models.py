"""
Modèles du module de gestion des commandes.

- Cart / CartItem : panier d'achat temporaire par utilisateur.
- Order / OrderItem : commande validée et ses lignes (snapshot des prix).
- OrderStatus : énumération des statuts possibles d'une commande.
- OrderStatusHistory : journal d'audit des changements de statut.
"""
import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.catalog.models import ProductVariant, Product
from apps.core.models import BaseModel


# =====================================================
# CART
# =====================================================

class Cart(BaseModel):
    """Panier d'achat d'un utilisateur (relation 1-to-1)."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="cart",
    )

    class Meta:
        db_table = "commandes_carts"
        verbose_name = "Panier"
        verbose_name_plural = "Paniers"

    def __str__(self):
        return f"Panier - {self.user.email}"




class CartItem(BaseModel):
    """Ligne de panier : un produit et sa quantité."""

    cart = models.ForeignKey(
        Cart,
        on_delete=models.CASCADE,
        related_name="items",
    )

    product = models.ForeignKey(
        ProductVariant,
        on_delete=models.CASCADE,
        related_name="cart_items",
    )

    quantity = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "commandes_cart_items"
        verbose_name = "Article de panier"
        verbose_name_plural = "Articles de panier"
        constraints = [
            models.UniqueConstraint(
                fields=["cart", "product"],
                name="unique_cartitem_cart_product",
            )
        ]

    def __str__(self):
        return f"{self.product.name} x {self.quantity}"

    @property
    def subtotal(self):
        return self.product.price * self.quantity






# =====================================================
# ORDER STATUS
# =====================================================

class OrderStatus(models.TextChoices):
    DRAFT = "draft", "Brouillon"
    PENDING_PAYMENT = "pending_payment", "Paiement en attente"
    PAID = "paid", "Payée"
    CONFIRMED = "confirmed", "Confirmée"
    PROCESSING = "processing", "Préparation"
    SHIPPED = "shipped", "Expédiée"
    DELIVERED = "delivered", "Livrée"
    CANCELLED = "cancelled", "Annulée"
    REFUNDED = "refunded", "Remboursée"





# =====================================================
# ORDER
# =====================================================

class Order(BaseModel):
    """
    Commande validée.

    La référence unique est générée automatiquement lors du premier save.
    Les montants sont dénormalisés (snapshot) pour garantir l'intégrité
    historique même si les prix du catalogue changent.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="orders",
    )

    reference = models.CharField(
        max_length=60,
        unique=True,
        blank=True,
        null=True,
        # db_index=True retiré : unique=True crée déjà l'index en DB.
    )

    status = models.CharField(
        max_length=30,
        choices=OrderStatus.choices,
        default=OrderStatus.PENDING_PAYMENT,
        db_index=True,
    )

    address_livraison = models.CharField(max_length=200)

    items_total = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
    )

    frais_livraison = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
    )

    discount_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
    )

    tax_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        null=True,
        blank=True,
    )

    total_final = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
    )

    notes = models.TextField(blank=True)

    phone_livraison = models.CharField(
        max_length=30,
        blank=True,
    )

    country = models.CharField(max_length=100)

    city = models.CharField(max_length=100)

    paid_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    class Meta:
        db_table = "commandes_orders"
        ordering = ["-created_at"]
        verbose_name = "Commande"
        verbose_name_plural = "Commandes"
        indexes = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["status", "-created_at"]),
        ]

    def __str__(self):
        return str(self.reference) if self.reference else f"Commande #{self.pk} (sans référence)"



# =====================================================
# ORDER ITEM
# =====================================================

class OrderItem(BaseModel):
    """
    Ligne de commande (snapshot immuable).

    product_name et product_sku sont copiés depuis le catalogue au moment
    de la commande pour garantir l'intégrité historique.
    """

    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="items",
    )

    # product = models.ForeignKey(
    #     Product,
    #     on_delete=models.PROTECT,
    # )


    product = models.ForeignKey(
        ProductVariant,
        on_delete=models.PROTECT,
    )

    product_name = models.CharField(max_length=255)

    product_sku = models.CharField(max_length=100)

    quantity = models.PositiveIntegerField()

    unit_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
    )

    subtotal = models.DecimalField(
        max_digits=12,
        decimal_places=2,
    )

    class Meta:
        db_table = "commandes_order_items"
        verbose_name = "Article commandé"
        verbose_name_plural = "Articles commandés"
        indexes = [
            models.Index(fields=["order"]),
        ]

    def __str__(self):
        return f"{self.product_name} x {self.quantity}"


# =====================================================
# ORDER STATUS HISTORY
# =====================================================

class OrderStatusHistory(BaseModel):
    """Journal d'audit de tous les changements de statut d'une commande."""

    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="status_history",
    )

    old_status = models.CharField(
        max_length=30,
        blank=True,
    )

    new_status = models.CharField(max_length=30)

    comment = models.TextField(blank=True)

    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    class Meta:
        db_table = "commandes_order_status_history"
        verbose_name = "Historique de statut"
        verbose_name_plural = "Historiques de statut"
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["order", "created_at"]),
        ]

    def __str__(self):
        return f"{self.order.reference} : {self.old_status} → {self.new_status}"
