"""
Serializers DRF pour le module promotions.

Séparation claire entre les serializers publics (lecture seule)
et les serializers d'administration (CRUD complet).
"""
from decimal import Decimal
from rest_framework import serializers

from .models import PromoCode, Soldes, Banner, Pack, PackItem
from apps.catalog.serializers import ProductVariantSerializer
from apps.catalog.models import ProductVariant


# ─── Public ────────────────────────────────────────────────────────────────

class PromoCodeListSerializer(serializers.ModelSerializer):
    """Affichage public des codes promo actifs (sans détails internes)."""
    type_display = serializers.CharField(
        source="get_type_display", read_only=True
    )

    class Meta:
        model = PromoCode
        fields = (
            "id",
            "code",
            "description",
            "type",
            "type_display",
            "value",
            "starts_at",
            "expires_at",
        )
        read_only_fields = fields


class ValidateCodeSerializer(serializers.Serializer):
    """Validation d'un code promo."""
    code = serializers.CharField(max_length=50)
    cart_total = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=Decimal("0.01")
    )

    def validate_code(self, value):
        return value.strip().upper()


class ApplyCodeSerializer(serializers.Serializer):
    """Application d'un code promo à une commande."""
    code = serializers.CharField(max_length=50)
    order_id = serializers.UUIDField()

    def validate_code(self, value):
        return value.strip().upper()

    def validate_order_id(self, value):
        from apps.commandes.models import Order
        try:
            order = Order.objects.get(pk=value)
        except Order.DoesNotExist:
            raise serializers.ValidationError("Commande introuvable.")
        if order.status not in ("draft", "pending_payment"):
            raise serializers.ValidationError(
                "Cette commande ne peut plus recevoir de code promo."
            )
        return value


class SoldesSerializer(serializers.ModelSerializer):
    """Affichage public d'une vente flash."""
    product_name = serializers.CharField(source="product.name", read_only=True)
    product_slug = serializers.CharField(source="product.slug", read_only=True)
    product_image = serializers.SerializerMethodField()
    discount_percent = serializers.IntegerField(read_only=True)
    remaining_stock = serializers.IntegerField(read_only=True, allow_null=True)

    class Meta:
        model = Soldes
        fields = (
            "id",
            "product_name",
            "product_slug",
            "product_image",
            "variant",
            "sale_price",
            "original_price",
            "discount_percent",
            "remaining_stock",
            "starts_at",
            "ends_at",
        )
        read_only_fields = fields

    def get_product_image(self, obj):
        # Utilise le cache prefetch_related("product__images") pour éviter le N+1
        primary = next(
            (img for img in obj.product.images.all() if img.is_primary),
            None
        )
        if primary and primary.image:
            request = self.context.get("request")
            if request:
                return request.build_absolute_uri(primary.image.url)
            return primary.image.url
        return None


class BannerSerializer(serializers.ModelSerializer):
    """Affichage public d'une bannière."""
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = Banner
        fields = (
            "id",
            "title",
            "subtitle",
            "image_url",
            "cta_label",
            "cta_url",
            "banner_type",
            "position",
        )
        read_only_fields = fields

    def get_image_url(self, obj):
        if obj.image:
            request = self.context.get("request")
            if request:
                return request.build_absolute_uri(obj.image.url)
            return obj.image.url
        return None


class PackItemVariantSerializer(serializers.ModelSerializer):
    """Variante sérialisée pour l'affichage dans les items de packs (inclut l'image du produit parent)."""
    product_name = serializers.CharField(source="product.name", read_only=True)
    product_slug = serializers.CharField(source="product.slug", read_only=True)
    product_primary_image = serializers.SerializerMethodField()

    class Meta:
        model = ProductVariant
        fields = (
            "id",
            "name",
            "price",
            "stock",
            "weight_grams",
            "is_active",
            "product_name",
            "product_slug",
            "product_primary_image",
        )

    def get_product_primary_image(self, obj):
        """Retourne l'URL absolue de l'image principale du produit parent."""
        primary = next(
            (img for img in obj.product.images.all() if img.is_primary),
            None,
        ) or next(iter(obj.product.images.all()), None)
        if primary and primary.image:
            request = self.context.get("request")
            if request:
                return request.build_absolute_uri(primary.image.url)
            return primary.image.url
        return None


class PackItemSerializer(serializers.ModelSerializer):
    """Article inclus dans un pack."""
    product_variant = PackItemVariantSerializer(read_only=True)
    
    class Meta:
        model = PackItem
        fields = ("id", "product_variant", "quantity")


class PackSerializer(serializers.ModelSerializer):
    """Affichage public d'un pack."""
    items = PackItemSerializer(many=True, read_only=True)
    image_url = serializers.SerializerMethodField()
    available_stock = serializers.SerializerMethodField()

    class Meta:
        model = Pack
        fields = (
            "id",
            "name",
            "slug",
            "description",
            "recette",
            "price",
            "image_url",
            "is_active",
            "items",
            "available_stock"
        )
        read_only_fields = fields

    def get_image_url(self, obj):
        if obj.image:
            request = self.context.get("request")
            if request:
                return request.build_absolute_uri(obj.image.url)
            return obj.image.url
        return None

    def get_available_stock(self, obj):
        from .services import PackService
        return PackService.calculate_pack_stock(obj)


# ─── Admin ────────────────────────────────────────────────────────────────

class AdminPromoCodeSerializer(serializers.ModelSerializer):
    """CRUD admin des codes promo."""

    class Meta:
        model = PromoCode
        fields = "__all__"
        read_only_fields = ("id", "created_at", "updated_at", "number_times_used")

    def validate(self, data):
        """Validation métier : pourcentage ≤ 100."""
        promo_type = data.get("type", self.instance.type if self.instance else None)
        promo_value = data.get("value", self.instance.value if self.instance else None)

        if promo_type == PromoCode.DiscountType.PERCENTAGE:
            if promo_value and promo_value > 100:
                raise serializers.ValidationError(
                    {"value": "Le pourcentage ne peut dépasser 100%."}
                )
        return data

    def to_representation(self, instance):
        from apps.catalog.serializers import ProductListSerializer, CategorySerializer
        representation = super().to_representation(instance)
        representation["applicable_products"] = ProductListSerializer(
            instance.applicable_products.all(), many=True, context=self.context
        ).data
        representation["applicable_categories"] = CategorySerializer(
            instance.applicable_categories.all(), many=True, context=self.context
        ).data
        return representation


class AdminSoldesSerializer(serializers.ModelSerializer):
    """CRUD admin des ventes flash."""

    class Meta:
        model = Soldes
        fields = "__all__"
        read_only_fields = ("id", "created_at", "updated_at", "original_price", "product_sold_count")

    def to_representation(self, instance):
        from apps.catalog.serializers import ProductListSerializer, ProductVariantSerializer
        representation = super().to_representation(instance)
        if instance.product:
            representation["product"] = ProductListSerializer(instance.product, context=self.context).data
        if instance.variant:
            representation["variant"] = ProductVariantSerializer(instance.variant, context=self.context).data
        return representation


class AdminBannerSerializer(serializers.ModelSerializer):
    """CRUD admin des bannières."""

    class Meta:
        model = Banner
        fields = "__all__"
        read_only_fields = ("id", "created_at", "updated_at")


class AdminPackItemInputSerializer(serializers.Serializer):
    """Serializer d'entrée pour les articles d'un pack (écriture uniquement)."""
    product_variant = serializers.UUIDField()
    quantity = serializers.IntegerField(min_value=1, default=1)
    is_active = serializers.BooleanField(default=True, required=False)


class AdminPackSerializer(serializers.ModelSerializer):
    """CRUD admin des packs."""
    items = PackItemSerializer(many=True, read_only=True)
    items_input = AdminPackItemInputSerializer(many=True, write_only=True, required=False, source="items")

    class Meta:
        model = Pack
        fields = "__all__"
        read_only_fields = ("id", "created_at", "updated_at", "slug")

    def create(self, validated_data):
        from apps.catalog.models import ProductVariant
        items_data = validated_data.pop("items", [])
        pack = Pack.objects.create(**validated_data)
        for item_data in items_data:
            variant_id = item_data.get("product_variant")
            try:
                variant = ProductVariant.objects.get(pk=variant_id)
                PackItem.objects.create(
                    pack=pack,
                    product_variant=variant,
                    quantity=item_data.get("quantity", 1),
                    is_active=item_data.get("is_active", True),
                )
            except ProductVariant.DoesNotExist:
                pass
        return pack

    def update(self, instance, validated_data):
        from apps.catalog.models import ProductVariant
        items_data = validated_data.pop("items", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if items_data is not None:
            instance.items.all().delete()
            for item_data in items_data:
                variant_id = item_data.get("product_variant")
                try:
                    variant = ProductVariant.objects.get(pk=variant_id)
                    PackItem.objects.create(
                        pack=instance,
                        product_variant=variant,
                        quantity=item_data.get("quantity", 1),
                        is_active=item_data.get("is_active", True),
                    )
                except ProductVariant.DoesNotExist:
                    pass
        return instance

