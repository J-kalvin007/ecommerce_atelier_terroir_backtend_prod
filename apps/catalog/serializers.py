from rest_framework import serializers

from .models import (
    Category,
    Product,
    ProductImage,
    ProductVariant,
)

from .models import Rating, Favorite
from django.db.models import Count




# =====================================================
# CATEGORY
# =====================================================

class CategorySerializer(serializers.ModelSerializer):
    children = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = (
            "id",
            "name",
            "slug",
            "description",
            "image",
            "parent",
            "children",
        )

    def get_children(self, obj):
        return CategorySerializer(
            obj.children.all(),
            many=True,
            context=self.context
        ).data


# =====================================================
# PRODUCT IMAGE
# =====================================================

class ProductImageSerializer(serializers.ModelSerializer):

    class Meta:
        model = ProductImage
        fields = (
            "id",
            "image",
            "alt_text",
            "is_primary",
            "created_at",
            "updated_at",
            "is_active",
        )

class ProductImageAdminSerializer(serializers.ModelSerializer):

    class Meta:
        model = ProductImage
        fields = (
            "id",
            "product",
            "image",
            "alt_text",
            "is_primary",
            "created_at",
            "updated_at",
            "is_active",
        )
        read_only_fields = (
            "id",
            "created_at",
            "updated_at",
        )


# =====================================================
# PRODUCT VARIANT
# =====================================================

class ProductVariantSerializer(serializers.ModelSerializer):

    is_in_stock = serializers.SerializerMethodField()

    class Meta:
        model = ProductVariant

        fields = (
            "id",
            "name",
            "sku",
            "price",
            "stock",
            "weight_grams",
            "is_in_stock",
            "created_at",
            "updated_at",
            "is_active",
        )

    def get_is_in_stock(self, obj):
        return obj.stock > 0

class ProductVariantAdminSerializer(serializers.ModelSerializer):

    class Meta:
        model = ProductVariant
        fields = (
            "id",
            "product",
            "name",
            "sku",
            "price",
            "stock",
            "weight_grams",
            "created_at",
            "updated_at",
            "is_active",
        )
        read_only_fields = (
            "id",
            "created_at",
            "updated_at",
        )


# =====================================================
# PRODUCT LIST
# =====================================================

class ProductListSerializer(serializers.ModelSerializer):

    primary_image = serializers.SerializerMethodField()

    category_name = serializers.CharField(
        source="category.name",
        read_only=True,
    )

    images = ProductImageSerializer(
        many=True,
        read_only=True,
    )

    variants = ProductVariantSerializer(
        many=True,
        read_only=True,
    )

    class Meta:
        model = Product

        fields = (
            "id",
            "name",
            "slug",
            "sku",
            "price",
            "discount_price",
            "stock",
            "is_top",
            "product_type",
            "category_name",
            "primary_image",
            "images",
            "variants",
            "note_produit",
            "count_ratings",
            "count_favorites",
            "order_count",
        )

    def get_primary_image(self, obj):
        image = obj.images.filter(
            is_primary=True
        ).first()

        if image:
            return ProductImageSerializer(image, context=self.context).data

        return None


# =====================================================
# PRODUCT DETAIL
# =====================================================

class ProductDetailSerializer(ProductListSerializer):

    images = ProductImageSerializer(
        many=True,
        read_only=True,
    )

    variants = ProductVariantSerializer(
        many=True,
        read_only=True,
    )

    related_products = ProductListSerializer(
        many=True,
        read_only=True,
    )

    category = CategorySerializer(
        read_only=True,
    )

    is_in_stock = serializers.SerializerMethodField()

    class Meta:
        model = Product

        fields = (
            "id",
            "name",
            "slug",
            "sku",
            "description",
            "product_type",
            "price",
            "discount_price",
            "stock",
            "weight_grams",
            "seo_title",
            "seo_description",
            "is_top",
            "is_in_stock",
            "category",
            "images",
            "variants",
            "related_products",
            "note_produit",
            "count_ratings",
            "count_favorites",
            "order_count",
            "created_at",
            "updated_at",
        )

    def get_is_in_stock(self, obj):
        return obj.stock > 0


# =====================================================
# PRODUCT CREATE / UPDATE
# =====================================================

class ProductCreateUpdateSerializer(
    serializers.ModelSerializer
):

    images = ProductImageSerializer(
        many=True,
        required=False,
    )

    class Meta:
        model = Product

        fields = (
            "id",
            "category",
            "name",
            "slug",
            "sku",
            "description",
            "product_type",
            "price",
            "discount_price",
            "stock",
            "weight_grams",
            "seo_title",
            "seo_description",
            "is_top",
            "related_products",
            "images",
        )
        read_only_fields = ("id",)

    def validate_sku(self, value):

        qs = Product.objects.filter(
            sku=value
        )

        if self.instance:
            qs = qs.exclude(
                pk=self.instance.pk
            )

        if qs.exists():
            raise serializers.ValidationError(
                "SKU already exists."
            )

        return value

    def create(self, validated_data):

        images_data = validated_data.pop(
            "images",
            []
        )

        product = Product.objects.create(
            **validated_data
        )

        for image_data in images_data:

            ProductImage.objects.create(
                product=product,
                **image_data
            )

        return product

    def update(
        self,
        instance,
        validated_data
    ):

        images_data = validated_data.pop(
            "images",
            None
        )

        for attr, value in validated_data.items():
            setattr(
                instance,
                attr,
                value
            )

        instance.save()

        if images_data:

            for image_data in images_data:

                ProductImage.objects.create(
                    product=instance,
                    **image_data
                )

        return instance
    






"""
Serializers pour le module de favoris.

Validation métier minimaliste : la logique de toggle est dans la vue,
le serializer ne fait que valider la présence et l'existence du product_id.
"""


class ToggleFavoriteSerializer(serializers.Serializer):
    """
    Serializer pour le endpoint de toggle de favori.
    
    Valide que le product_id fourni existe bien dans la base.
    """
    product_id = serializers.UUIDField()

    def validate_product_id(self, value):
        """Vérifie que le produit existe et est actif."""
        

        try:
            product = Product.objects.get(pk=value, is_active=True)
        except Product.DoesNotExist:
            raise serializers.ValidationError(
                "Produit introuvable ou inactif."
            )
        return value




class FavoriteProductSerializer(serializers.Serializer):
    """
    Serializer pour l'affichage d'un produit dans la liste des favoris.
    
    Inclut les informations essentielles du produit pour l'affichage
    dans l'interface utilisateur (pas de nested serializer Product complet
    pour éviter de coupler les applications).
    """
    id = serializers.UUIDField(source="product.id")
    name = serializers.CharField(source="product.name")
    slug = serializers.CharField(source="product.slug")
    price = serializers.DecimalField(
        source="product.effective_price",
        max_digits=12,
        decimal_places=2,
    )
    image = serializers.SerializerMethodField()
    is_in_stock = serializers.BooleanField(source="product.is_in_stock")
    favorited_at = serializers.DateTimeField(source="created_at")
    count_favorites = serializers.IntegerField(
        source="product.count_favorites",
        default=0,
        help_text="Nombre total de favoris pour ce produit"
    )
    default_variant_id = serializers.SerializerMethodField()

    def get_default_variant_id(self, obj):
        first_variant = obj.product.variants.filter(is_active=True).first()
        return str(first_variant.id) if first_variant else None

    def get_image(self, obj):
        """Retourne l'URL de l'image principale du produit si elle existe."""
        primary_image = obj.product.images.filter(is_primary=True).first()
        if primary_image and primary_image.image:
            request = self.context.get("request")
            if request:
                return request.build_absolute_uri(primary_image.image.url)
            return primary_image.image.url
        return None
    













"""
Serializers pour le module de notation.

- RateSerializer : validation de la note (0-5) et du product_id.
- RatingDetailSerializer : distribution par étoile et note utilisateur.
"""



class RateSerializer(serializers.Serializer):
    """
    Serializer pour créer ou modifier une note.
    
    Valide que le score est dans l'intervalle 0-5 et que le produit existe.
    """
    product_id = serializers.UUIDField()
    score = serializers.IntegerField(min_value=0, max_value=5)

    def validate_product_id(self, value):
        """Vérifie que le produit existe et est actif."""
        from apps.catalog.models import Product

        try:
            product = Product.objects.get(pk=value, is_active=True)
        except Product.DoesNotExist:
            raise serializers.ValidationError(
                "Produit introuvable ou inactif."
            )
        return value


class RatingDetailSerializer(serializers.Serializer):
    """
    Serializer pour la réponse détaillée de notation d'un produit.
    
    Inclut :
    - La distribution des notes (combien de 1★, 2★, ..., 5★)
    - La note moyenne globale
    - Le nombre total de notes
    - La note de l'utilisateur connecté (null si non noté)
    """
    product_id = serializers.UUIDField(source="product.id")
    product_name = serializers.CharField(source="product.name")
    note_produit = serializers.DecimalField(
        max_digits=3,
        decimal_places=2,
        source="product.note_produit",
    )
    count_ratings = serializers.IntegerField(source="product.count_ratings", help_text="Nombre total de notes")
    distribution = serializers.SerializerMethodField()
    user_score = serializers.SerializerMethodField()

    def get_distribution(self, obj):
        """
        Calcule la distribution des notes pour le produit.
        
        Returns:
            dict: {1: count, 2: count, 3: count, 4: count, 5: count}
        """
        

        distribution = (
            Rating.objects
            .filter(product=obj)
            .values("score")
            .annotate(count=Count("id"))
            .order_by("score")
        )
        # Initialiser toutes les étoiles de 1 à 5
        result = {str(i): 0 for i in range(1, 6)}
        for entry in distribution:
            result[str(entry["score"])] = entry["count"]
        return result
    


    def get_user_score(self, obj):
        """
        Retourne la note de l'utilisateur connecté pour ce produit,
        ou None s'il n'a pas encore noté.
        """
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return None

        
        try:
            rating = Rating.objects.get(user=request.user, product=obj)
            return rating.score
        except Rating.DoesNotExist:
            return None