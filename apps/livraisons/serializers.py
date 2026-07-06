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
    order_reference = serializers.CharField(source="order.reference", read_only=True)
    delivery_person_name = serializers.CharField(source="delivery_person.email", read_only=True)

    class Meta:
        model = Delivery
        fields = [
            "id",
            "order",
            "order_reference",
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
