"""
Modèles du module promotions.

- PromoCode : codes promotionnels avec règles métier avancées
- PromoUsage : traçabilité anti-double-usage
- Soldes : ventes flash avec prix et stock limités
- Banner : bannières marketing pour l'affichage frontend
"""
import uuid
from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.db.models import F
from django.utils import timezone

from apps.core.models import BaseModel


class PromoCode(BaseModel):
    """
    Code promotionnel avec règles métier configurables.

    Supports :
    - Réduction en pourcentage (avec plafond) ou montant fixe
    - Livraison gratuite
    - Restrictions par produits, catégories, paliers de fidélité
    - Quotas global et par utilisateur
    - Période de validité

    Note: number_times_used est incrémenté atomiquement via F() expression
    pour éviter les race conditions en haute concurrence.
    """

    class DiscountType(models.TextChoices):
        PERCENTAGE = "percentage", "Pourcentage (%)"
        FIXED_AMOUNT = "fixed_amount", "Montant fixe (FCFA)"
        FREE_SHIPPING = "free_shipping", "Livraison gratuite"


    code = models.CharField(
        max_length=50,
        unique=True,
        db_index=True,
        help_text="Code promo saisi par le client. Auto-généré si vide.",
    )

    description = models.TextField(
        blank=True,
        help_text="Description interne de la campagne.",
    )

    type = models.CharField(
        max_length=20,
        choices=DiscountType.choices,
        default=DiscountType.PERCENTAGE,
    )

    value = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text="Valeur de la réduction (%, FCFA).",
    )

    number_times_used = models.PositiveIntegerField(
        default=0,
        editable=False,
        help_text="Compteur d'utilisations (incrémenté atomiquement).",
    )

    applicable_products = models.ManyToManyField(
        "catalog.Product",
        blank=True,
        related_name="promo_codes",
        help_text="Produits éligibles (vide = tous).",
    )

    applicable_categories = models.ManyToManyField(
        "catalog.Category",
        blank=True,
        related_name="promo_codes",
        help_text="Catégories éligibles (vide = toutes).",
    )

    restricted_to_tiers = models.ManyToManyField(
        "fidelites.LoyaltyTier",
        blank=True,
        related_name="restricted_promo_codes",
        help_text="Paliers de fidélité autorisés (vide = tous).",
    )

    starts_at = models.DateTimeField(
        default=timezone.now,
        help_text="Date de début de validité.",
    )

    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Date d'expiration. Null = pas d'expiration.",
    )


    class Meta:
        db_table = "promotions_promo_codes"
        verbose_name = "Code promo"
        verbose_name_plural = "Codes promo"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["code"]),
            models.Index(fields=["is_active", "starts_at", "expires_at"]),
        ]


    def __str__(self):
        return f"{self.code} ({self.get_type_display()})"


    def save(self, *args, **kwargs):
        # """Auto-génère un code unique si non fourni."""
        # if not self.code:
        #     self.code = f"PROMO-{uuid.uuid4().hex[:8].upper()}"
        # Validation : si PERCENTAGE, limiter à 100
        if self.type == self.DiscountType.PERCENTAGE:
            if self.value > 100:
                raise ValueError("Le pourcentage de réduction ne peut dépasser 100%.")
        super().save(*args, **kwargs)


    @property
    def is_valid(self) -> bool:
        """
        Vérifie si le code promo est actif et dans sa période de validité.
        """
        now = timezone.now()
        if not self.is_active:
            return False
        if self.starts_at and now < self.starts_at:
            return False
        if self.expires_at and now > self.expires_at:
            return False
        return True



    def calculate_discount(
        self,
        cart_total: Decimal,
        cart_items: list = None,
    ) -> Decimal:
        """
        Calcule le montant de réduction pour un panier donné.

        Args:
            cart_total: Montant total du panier (Decimal).
            cart_items: Liste optionnelle de dicts {product_id, category_id, price}
                        pour les restrictions par produit/catégorie.

        Returns:
            Decimal: Montant de la réduction calculée.
        """
        cart_total = cart_total.quantize(Decimal("0.01"))

        if self.type == self.DiscountType.FREE_SHIPPING:
            # La livraison gratuite est gérée côté commande
            return Decimal("0.00")

        if self.type == self.DiscountType.FIXED_AMOUNT:
            discount = min(self.value, cart_total)
            return discount.quantize(Decimal("0.01"))

        # PERCENTAGE
        discount = (cart_total * self.value / 100).quantize(Decimal("0.01"))

        return discount.quantize(Decimal("0.01"))

    def get_user_usage_count(self, user) -> int:
        """Retourne le nombre de fois que cet utilisateur a utilisé ce code."""
        return PromoUsage.objects.filter(promo_code=self, user=user).count()


# class PromoUsage(BaseModel):
#     """
#     Traçabilité d'utilisation d'un code promo.

#     La contrainte unique_together (promo_code, user, order_id) garantit
#     qu'un code ne peut être utilisé qu'une fois par utilisateur et par commande,
#     même en cas de requêtes concurrentes.
#     """
#     promo_code = models.ForeignKey(
#         PromoCode,
#         on_delete=models.PROTECT,
#         related_name="usages",
#     )

#     user = models.ForeignKey(
#         settings.AUTH_USER_MODEL,
#         on_delete=models.PROTECT,
#         related_name="promo_usages",
#     )

#     order = models.ForeignKey(
#         "commandes.Order",
#         on_delete=models.PROTECT,
#         related_name="promo_usages",
#         help_text="Commande sur laquelle le code a été appliqué.",
#     )

#     discount_applied = models.DecimalField(
#         max_digits=12,
#         decimal_places=2,
#         help_text="Montant de réduction effectivement appliqué.",
#     )


#     class Meta:
#         db_table = "promotions_promo_usages"
#         verbose_name = "Utilisation code promo"
#         verbose_name_plural = "Utilisations codes promo"
#         unique_together = [("promo_code", "user", "order")]  # Anti-double-usage
#         indexes = [
#             models.Index(fields=["promo_code", "user"]),
#             models.Index(fields=["order"]),
#         ]

#     def __str__(self):
#         return f"{self.promo_code.code} × {self.user.email} ({self.discount_applied} FCFA)"

#     @classmethod
#     def get_user_usage_count(cls, promo_code, user) -> int:
#         """Compte les utilisations d'un code par un utilisateur spécifique."""
#         return cls.objects.filter(promo_code=promo_code, user=user).count()


class Soldes(BaseModel):
    """
    Soldes : prix réduit temporaire sur un produit ou une variante.

    - Prix soldé avec quota de stock limité
    - Pourcentage de réduction auto-calculé
    - Compteur de ventes incrémenté atomiquement via F()
    """

    product = models.ForeignKey(
        "catalog.Product",
        on_delete=models.CASCADE,
        related_name="soldes",
    )

    variant = models.ForeignKey(
        "catalog.ProductVariant",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="soldes",
    )

    sale_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
        help_text="Prix soldé.",
    )

    original_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        editable=False,
        help_text="Prix original snapshot au moment de la création.",
    )

    quota_stock_limit = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Quota maximum de ventes au prix soldé (null = illimité).",
    )

    product_sold_count = models.PositiveIntegerField(
        default=0,
        editable=False,
        help_text="Nombre de ventes effectuées (incrémenté atomiquement).",
    )

    starts_at = models.DateTimeField(
        default=timezone.now,
        help_text="Début de la vente flash.",
    )

    ends_at = models.DateTimeField(
        help_text="Fin de la vente flash.",
    )


    class Meta:
        db_table = "promotions_soldes"
        verbose_name = "Solde"
        verbose_name_plural = "Soldes"
        ordering = ["-starts_at"]
        indexes = [
            models.Index(fields=["is_active", "starts_at", "ends_at"]),
            models.Index(fields=["product"]),
        ]

    def __str__(self):
        product_name = self.variant.name if self.variant else self.product.name
        return f"Flash: {product_name} à {self.sale_price} FCFA"

    def save(self, *args, **kwargs):
        """Snapshot du prix original à la création."""
        if not self.original_price:
            if self.variant:
                self.original_price = self.variant.price
            else:
                self.original_price = self.product.effective_price
        super().save(*args, **kwargs)

    @property
    def discount_percent(self) -> int:
        """Pourcentage de réduction auto-calculé."""
        if self.original_price and self.original_price > 0:
            return round(
                ((self.original_price - self.sale_price) / self.original_price) * 100
            )
        return 0

    @property
    def is_running(self) -> bool:
        """
        Vérifie si la vente en solde est en cours d'exécution.

        Conditions : active + dans l'intervalle de temps + stock non épuisé.
        """
        if not self.is_active:
            return False
        now = timezone.now()
        if now < self.starts_at or now > self.ends_at:
            return False
        if self.quota_stock_limit is not None and self.product_sold_count >= self.quota_stock_limit:
            return False
        return True


    @property
    def remaining_stock(self):
        """Stock restant au prix soldé (None si illimité)."""
        if self.quota_stock_limit is None:
            return None
        return max(0, self.quota_stock_limit - self.product_sold_count)


class Banner(BaseModel):
    """
    Bannière marketing pour le frontend.

    Types : CAROUSEL, POPUP, HERO, SIDE_BANNER
    Ordonnées par position pour l'affichage.
    """

    class BannerType(models.TextChoices):
        CAROUSEL = "carousel", "Carrousel"
        POPUP = "popup", "Popup"
        HERO = "hero", "Hero / En-tête"
        SIDE_BANNER = "side_banner", "Bannière latérale"

    title = models.CharField(max_length=255)

    subtitle = models.CharField(max_length=500, blank=True)

    image = models.ImageField(
        upload_to="banners/%Y/%m/",
        help_text="Image de la bannière (optimisée pour le type).",
    )

    cta_label = models.CharField(
        max_length=100,
        blank=True,
        help_text="Texte du bouton d'action.",
    )

    cta_url = models.URLField(
        max_length=500,
        blank=True,
        help_text="URL de destination du clic.",
    )

    banner_type = models.CharField(
        max_length=20,
        choices=BannerType.choices,
        default=BannerType.HERO,
        db_index=True,
    )

    position = models.PositiveIntegerField(
        default=0,
        help_text="Ordre d'affichage (0 = premier).",
    )

    starts_at = models.DateTimeField(
        default=timezone.now,
    )

    ends_at = models.DateTimeField(
        null=True,
        blank=True,
    )


    class Meta:
        db_table = "promotions_banners"
        verbose_name = "Bannière"
        verbose_name_plural = "Bannières"
        ordering = ["banner_type", "position", "-created_at"]
        indexes = [
            models.Index(fields=["banner_type", "is_active"]),
        ]

    def __str__(self):
        return f"{self.get_banner_type_display()}: {self.title}"


    @property
    def is_running(self) -> bool:
        """Vérifie si la bannière doit être affichée maintenant."""
        if not self.is_active:
            return False
        now = timezone.now()
        if now < self.starts_at:
            return False
        if self.ends_at and now > self.ends_at:
            return False
        return True