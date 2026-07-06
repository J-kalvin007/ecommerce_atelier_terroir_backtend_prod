"""
Serializers DRF pour le module de fidélisation.
"""
from decimal import Decimal
from rest_framework import serializers
from .models import LoyaltyTier, LoyaltyProfile, LoyaltyEvent, PointValue, LoyaltyRewardRule
from ecommerce_backend.users.serializers import UserSerializer


class PointValueSerializer(serializers.ModelSerializer):
    """Configuration publique de la valeur des points."""
    class Meta:
        model = PointValue
        fields = (
            "nombre_de_point",
            "valeur_un_point_frcfa",
            "duree_validite",
        )
        read_only_fields = fields


class AdminPointValueSerializer(serializers.ModelSerializer):
    """Configuration complète de la valeur des points pour l'admin."""
    class Meta:
        model = PointValue
        fields = "__all__"


class LoyaltyRewardRuleSerializer(serializers.ModelSerializer):
    """Règles de gain pour l'admin."""
    class Meta:
        model = LoyaltyRewardRule
        fields = "__all__"


class TierSerializer(serializers.ModelSerializer):
    """Affichage public d'un palier de fidélité."""
    class Meta:
        model = LoyaltyTier
        fields = (
            "id",
            "name",
            "min_points",
            "min_solde",
            "discount_percent",
        )
        read_only_fields = fields





class AdminTierSerializer(serializers.ModelSerializer):
    """Gestion CRUD des paliers par un administrateur."""
    class Meta:
        model = LoyaltyTier
        fields = (
            "id",
            "name",
            "min_points",
            "min_solde",
            "discount_percent",
        )
        read_only_fields = ("id",)




class LoyaltyProfileSerializer(serializers.ModelSerializer):
    """Profil de fidélité complet de l'utilisateur connecté."""
    tier = TierSerializer(read_only=True)
    tier_name = serializers.CharField(source="tier.name", read_only=True)
    next_tier = serializers.SerializerMethodField()
    user = UserSerializer(read_only=True)

    class Meta:
        model = LoyaltyProfile
        fields = (
            "id",
            "user",
            "tier",
            "tier_name",
            "points_balance",
            "total_points_gagne",
            "total_solde",
            "next_tier",
            "created_at",
        )
        read_only_fields = fields

    def get_next_tier(self, obj):
        """
        Retourne le prochain palier à atteindre, ou None si déjà au max.
        """
        current = obj.tier
        if not current:
            return None
        next_tier = LoyaltyTier.objects.filter(
            min_points__gt=current.min_points
        ).order_by("min_points").first()

        if next_tier:
            points_needed = next_tier.min_points - obj.total_points_gagne
            return {
                "name": next_tier.name,
                "points_needed": max(0, points_needed),
            }
        return None





class LoyaltyEventSerializer(serializers.ModelSerializer):
    """Journal des événements de points."""
    reason_display = serializers.CharField(source="get_reason_display", read_only=True)

    class Meta:
        model = LoyaltyEvent
        fields = (
            "id",
            "points_delta",
            "new_points_balance_after",
            "reason",
            "reason_display",
            "description",
            "created_at",
        )
        read_only_fields = fields






class RedeemPointsSerializer(serializers.Serializer):
    """Demande de dépense de points."""
    points_to_spend = serializers.IntegerField(min_value=1)
    order_id = serializers.UUIDField()

    def validate_order_id(self, value):
        from apps.commandes.models import Order
        try:
            order = Order.objects.get(
                pk=value, user=self.context["request"].user
            )
        except Order.DoesNotExist:
            raise serializers.ValidationError("Commande introuvable.")
        if order.status not in ("draft", "pending_payment"):
            raise serializers.ValidationError(
                "Cette commande ne peut plus recevoir de réduction."
            )
        return value





class AdminAdjustPointsSerializer(serializers.Serializer):
    """Ajustement manuel de points par un administrateur."""
    user_id = serializers.UUIDField()
    points = serializers.IntegerField()
    reason = serializers.CharField(max_length=255)

    def validate_points(self, value):
        if value == 0:
            raise serializers.ValidationError("Le delta de points ne peut être zéro.")
        return value
