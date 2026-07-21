from rest_framework import serializers
from .models import FraisLivraison, Delivery

class FraisLivraisonSerializer(serializers.ModelSerializer):
    class Meta:
        model = FraisLivraison
        fields = [
            "id",
            "prix_livraison",
            "coordonnee_admin",
            "created_at",
            "updated_at",
            "is_active"
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

class FraisLivraisonPublicSerializer(serializers.ModelSerializer):
    class Meta:
        model = FraisLivraison
        fields = [
            "prix_livraison",
            "coordonnee_admin"
        ]


class DeliverySerializer(serializers.ModelSerializer):
    order_reference = serializers.SerializerMethodField()
    order_status = serializers.CharField(source="order.status", read_only=True)
    client_name = serializers.SerializerMethodField()
    client_phone = serializers.CharField(source="order.phone_livraison", read_only=True)
    delivery_person_name = serializers.CharField(source="delivery_person.email", read_only=True, allow_null=True)
    order_total = serializers.DecimalField(source="order.total_final", max_digits=12, decimal_places=2, read_only=True)
    items_count = serializers.SerializerMethodField()

    class Meta:
        model = Delivery
        fields = [
            "id",
            "order",
            "order_reference",
            "order_status",
            "client_name",
            "client_phone",
            "order_total",
            "items_count",
            "status",
            "delivery_address",
            "tracking_number",
            "delivery_person",
            "delivery_person_name",
            "estimated_delivery_date",
            "actual_delivery_date",
            "notes",
            "created_at",
            "updated_at",
            "is_active"
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_items_count(self, obj):
        return sum(item.quantity for item in obj.order.items.all())

    def get_order_reference(self, obj):
        return obj.order.numero_commande or obj.order.reference or str(obj.order.id)

    def get_client_name(self, obj):
        order = obj.order
        if order.prenom_client and order.nom_client:
            return f"{order.prenom_client} {order.nom_client}"
        if order.user:
            return order.user.get_full_name() or order.user.email
        return order.nom_client or order.prenom_client or "—"
