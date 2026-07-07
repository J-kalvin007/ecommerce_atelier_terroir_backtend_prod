from apps.core.models import BaseModel
from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator





class Category(BaseModel):
    name = models.CharField(max_length=100)

    slug = models.SlugField(
        unique=True,
        db_index=True,
        null=True,
        blank=True
    )

    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="children",
    )

    description = models.TextField(blank=True)

    image = models.ImageField(
        upload_to="categories/",
        blank=True,
        null=True,
    )

    class Meta:
        verbose_name = "Catégorie"
        verbose_name_plural = "Catégories"
        ordering = ["name"]

    def __str__(self):
        return self.name





class Product(BaseModel):

    class ProductType(models.TextChoices):
        RAW = "RAW", "Brut"
        PROCESSED = "PROCESSED", "Transformé"
        EXPORT = "EXPORT", "Export"

    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name="products",
    )

    name = models.CharField(max_length=255)

    slug = models.SlugField(
        unique=True,
        db_index=True,
        null=True,
        blank=True
    )

    sku = models.CharField(
        max_length=100,
        unique=True,
        db_index=True,
    )

    description = models.TextField(
        null=True,
        blank=True
    )

    product_type = models.CharField(
        max_length=20,
        choices=ProductType.choices,
    )

    price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
    )

    stock = models.PositiveIntegerField(
        default=0,
        null=False,
        blank=False,
    )

    weight_grams = models.PositiveIntegerField(
        null=True,
        blank=True,
    )

    seo_title = models.CharField(
        max_length=255,
        blank=True,
        null=True,
    )

    seo_description = models.TextField(
        blank=True,
        null=True,
    )

    is_top = models.BooleanField(
        default=False,
        null=True,
        blank=True,
    )

    discount_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
    )

    order_count = models.PositiveIntegerField(
        default=0,
        db_index=True,
        editable=False,
        help_text="Nombre de commandes contenant ce produit (recalculé par signal).",
    )

    count_favorites = models.PositiveIntegerField(
        default=0,
        editable=False,
        help_text="Nombre de favoris (dénormalisé, recalculé par signal).",
    )


    note_produit = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        default=0.00,
        editable=False,
        help_text="Note moyenne du produit (dénormalisé, recalculé par signal).",
    )

    count_ratings = models.PositiveIntegerField(
        default=0,
        editable=False,
        help_text="Nombre de notes (dénormalisé, recalculé par signal).",
    )

    related_products = models.ManyToManyField(
        "self",
        blank=True,
    )

    class Meta:
        verbose_name = "Produit"
        verbose_name_plural = "Produits"
        ordering = ["-created_at"]

        indexes = [
            models.Index(fields=["slug"]),
            models.Index(fields=["sku"]),
            models.Index(fields=["price"]),
            models.Index(fields=["is_active"]),
        ]

    @property
    def is_in_stock(self):
        return self.stock > 0


    @property
    def effective_price(self):

        first_variant = self.variants.first()

        if first_variant:
            return first_variant.price

        return self.price


    
    @property
    def effective_stock(self):

        first_variant = self.variants.first()

        if first_variant:
            total = self.variants.aggregate(total_stock=models.Sum("stock"))["total_stock"]
            return total if total is not None else 0

        return self.stock


    

    # @property
    # def discount_percentage(self):
    #     if self.compare_price and self.compare_price > self.price:
    #         return round(
    #             (
    #                 (self.compare_price - self.price)
    #                 / self.compare_price
    #             ) * 100
    #         )
    #     return 0

    def __str__(self):
        return self.name








class ProductImage(BaseModel):

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="images",
    )

    image = models.ImageField(
        upload_to="products/%Y/%m/",
    )

    alt_text = models.CharField(
        max_length=255,
        blank=True,
    )

    is_primary = models.BooleanField(
        default=False,
    )

    class Meta:
        verbose_name = "Image Produit"
        verbose_name_plural = "Images Produit"
        ordering = ["-is_primary"]

    def __str__(self):
        return self.product.name






class ProductVariant(BaseModel):

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="variants",
    )

    name = models.CharField(
        max_length=100,
    )

    sku = models.CharField(
        max_length=100,
        unique=True,
        db_index=True,
        null=True,
        blank=True
    )

    price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
    )

    stock = models.PositiveIntegerField(
        default=0,
        null=False,
        blank=False,
    )

    weight_grams = models.PositiveIntegerField(
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = "Variante Produit"
        verbose_name_plural = "Variantes Produit"
        ordering = ["name"]

    def __str__(self):
        return f"{self.product.name} - {self.name}"








"""
Modèle Favorite pour le système de wishlist.

Contrainte d'unicité stricte au niveau base de données sur le couple
(user, product) pour garantir l'intégrité et éviter les doublons en race condition.
"""

class Favorite(BaseModel):
    """
    Association favorite entre un utilisateur et un produit.
    
    La contrainte unique_together est appliquée au niveau de la base de données
    pour garantir l'atomicité des opérations de toggle même en cas de requêtes
    concurrentes.
    
    Attributes:
        user: Utilisateur qui a mis en favori.
        product: Produit mis en favori.
        created_at: Date d'ajout aux favoris.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="favorites",
    )

    product = models.ForeignKey(
        "catalog.Product",
        on_delete=models.CASCADE,
        related_name="favorites",
    )

    class Meta:
        db_table = "favorites_favorites"
        verbose_name = "Favori"
        verbose_name_plural = "Favoris"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["user", "product"], name="unique_favorite_user_product")
        ]
        indexes = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["product", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.user.email} ♥ {self.product.name}"
    






    """
Modèle Rating pour le système de notation par étoiles (0-5).

Contrainte d'unicité au niveau DB sur (user, product) : un utilisateur
ne peut avoir qu'une seule note par produit. La modification se fait
via update_or_create (upsert).
"""


class Rating(BaseModel):
    """
    Note attribuée par un utilisateur à un produit.
    
    Score compris entre 0 et 5 étoiles. La contrainte UniqueConstraint
    garantit qu'un utilisateur ne peut noter un produit qu'une seule fois.
    
    Attributes:
        user: Utilisateur qui note.
        product: Produit noté.
        score: Note de 0 à 5.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="ratings",
    )

    product = models.ForeignKey(
        "catalog.Product",
        on_delete=models.CASCADE,
        related_name="ratings",
    )

    score = models.PositiveSmallIntegerField(
        validators=[
            MinValueValidator(0, message="La note minimale est 0."),
            MaxValueValidator(5, message="La note maximale est 5."),
        ],
        help_text="Note de 0 à 5 étoiles",
    )

  

    class Meta:
        db_table = "ratings_ratings"
        verbose_name = "Note"
        verbose_name_plural = "Notes"
        ordering = ["-updated_at"]
        constraints = [
            models.UniqueConstraint(fields=["user", "product"], name="unique_rating_user_product")
        ]
        indexes = [
            models.Index(fields=["product", "-updated_at"]),
            models.Index(fields=["user", "-updated_at"]),
        ]

    def __str__(self):
        return f"{self.user.email} → {self.product.name} : {self.score}★"