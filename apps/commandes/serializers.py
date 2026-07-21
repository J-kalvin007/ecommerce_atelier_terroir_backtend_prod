from rest_framework import serializers

from apps.commandes.models import Order, OrderItem, OrderStatus, OrderStatusHistory, Cart, CartItem
from ecommerce_backend.users.api.serializers import UserSerializer
from apps.catalog.serializers import ProductVariantSerializer


# =====================================================
# CHECKOUT
# =====================================================

class CheckoutItemSerializer(serializers.Serializer):
    product_id = serializers.UUIDField()
    quantity = serializers.IntegerField(min_value=1)


class CheckoutSerializer(serializers.Serializer):
    nom_client = serializers.CharField(max_length=100, required=False, allow_blank=True)
    prenom_client = serializers.CharField(max_length=100, required=False, allow_blank=True)
    email_client = serializers.EmailField(required=False, allow_blank=True)
    address_livraison = serializers.CharField(max_length=255)
    phone_livraison = serializers.CharField(max_length=30)
    city = serializers.CharField(max_length=100)
    country = serializers.CharField(max_length=100)
    notes = serializers.CharField(required=False, allow_blank=True)
    frais_livraison = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, default=0)
    discount_amount = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, default=0)
    is_for_delivery = serializers.BooleanField(default=True)
    items = CheckoutItemSerializer(many=True)

    def validate_items(self, value):
        if not value:
            raise serializers.ValidationError("La commande doit contenir au moins un produit.")
        return value


# =====================================================
# ORDER ITEM
# =====================================================

class OrderItemSerializer(serializers.ModelSerializer):
    product_details = ProductVariantSerializer(source='product', read_only=True)

    class Meta:
        model = OrderItem
        fields = (
            "id",
            "product",
            "product_details",
            "product_name",
            "product_sku",
            "quantity",
            "unit_price",
            "subtotal",
        )


# =====================================================
# ORDER LIST
# =====================================================

class OrderListSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    items = OrderItemSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = (
            "id",
            "numero_commande",
            "reference",
            "user",
            "nom_client",
            "prenom_client",
            "email_client",
            "status",
            "is_for_delivery",
            "items_total",
            "frais_livraison",
            "total_final",
            "created_at",
            "items",
        )


# =====================================================
# ORDER DETAIL
# =====================================================

class OrderDetailSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    user = UserSerializer(read_only=True)

    class Meta:
        model = Order
        fields = (
            "id",
            "numero_commande",
            "reference",
            "user",
            "nom_client",
            "prenom_client",
            "email_client",
            "status",
            "is_for_delivery",
            "address_livraison",
            "phone_livraison",
            "city",
            "country",
            "items_total",
            "frais_livraison",
            "discount_amount",
            "tax_amount",
            "total_final",
            "notes",
            "paid_at",
            "created_at",
            "updated_at",
            "items",
        )


# =====================================================
# ORDER HISTORY
# =====================================================

class OrderHistorySerializer(serializers.ModelSerializer):
    changed_by_email = serializers.SerializerMethodField()

    class Meta:
        model = OrderStatusHistory
        fields = (
            "id",
            "old_status",
            "new_status",
            "comment",
            "created_at",
            "changed_by_email",
        )

    def get_changed_by_email(self, obj):
        if not obj.changed_by:
            return None
        return obj.changed_by.email


# =====================================================
# ADMIN UPDATE STATUS
# =====================================================

class AdminOrderStatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=OrderStatus.choices)
    comment = serializers.CharField(required=False, allow_blank=True)


# =====================================================
# CART ITEM
# =====================================================

class CartItemSerializer(serializers.ModelSerializer):
    product_details = ProductVariantSerializer(source='product', read_only=True)
    subtotal = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    
    parent_product_id = serializers.UUIDField(source='product.product.id', read_only=True)
    slug = serializers.CharField(source='product.product.slug', read_only=True)
    primary_image = serializers.SerializerMethodField()

    class Meta:
        model = CartItem
        fields = (
            "id",
            "product",
            "product_details",
            "quantity",
            "subtotal",
            "parent_product_id",
            "slug",
            "primary_image"
        )

    def get_primary_image(self, obj):
        image = obj.product.product.images.filter(is_primary=True).first()
        if image and image.image:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(image.image.url)
            return image.image.url
        return None

class AddCartItemSerializer(serializers.Serializer):
    product_id = serializers.UUIDField()
    quantity = serializers.IntegerField(min_value=1)


# =====================================================
# CART
# =====================================================

class CartSerializer(serializers.ModelSerializer):
    items = CartItemSerializer(many=True, read_only=True)
    total = serializers.SerializerMethodField()
    item_count = serializers.SerializerMethodField()

    class Meta:
        model = Cart
        fields = (
            "id",
            "user",
            "items",
            "total",
            "item_count",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("user", "created_at", "updated_at")

    def get_total(self, obj):
        return sum(item.subtotal for item in obj.items.all())

    def get_item_count(self, obj):
        return sum(item.quantity for item in obj.items.all())