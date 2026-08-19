"""
Serializers DRF pour le module recettes.

Séparation entre l'affichage public (lecture seule, façon page recette
d'un site e-commerce) et l'administration (CRUD complet réservé aux
administrateurs de la plateforme).
"""
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from .models import Recette


# =====================================================
# PUBLIC
# =====================================================

class RecetteSerializer(serializers.ModelSerializer):
    """
    Affichage public d'une recette de cuisine : ingrédients, instructions,
    vidéo et visuels, avec un aperçu du produit ou du pack associé.
    """

    product_name = serializers.CharField(
        source="product.name",
        read_only=True,
    )

    product_slug = serializers.CharField(
        source="product.slug",
        read_only=True,
    )

    pack_name = serializers.CharField(
        source="pack.name",
        read_only=True,
    )

    pack_slug = serializers.CharField(
        source="pack.slug",
        read_only=True,
    )

    class Meta:
        model = Recette

        fields = (
            "id",
            "nom",
            "slug",
            "description",
            "ingredients",
            "instructions",
            "video_url",
            "video",
            "image_1",
            "image_2",
            "product",
            "product_name",
            "product_slug",
            "pack",
            "pack_name",
            "pack_slug",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


# =====================================================
# ADMIN
# =====================================================

class AdminRecetteSerializer(serializers.ModelSerializer):
    """CRUD admin complet des recettes de cuisine."""

    class Meta:
        model = Recette
        fields = "__all__"
        read_only_fields = ("id", "created_at", "updated_at")

    def validate(self, attrs):
        """
        Une recette ne peut être rattachée qu'à un seul produit OU un seul
        pack à la fois (jamais les deux). Cette règle est également
        garantie en base par une contrainte CHECK (voir Recette.Meta), mais
        on la valide ici en amont pour renvoyer une erreur 400 lisible côté
        API plutôt qu'une IntegrityError brute.
        """
        product = attrs.get("product", getattr(self.instance, "product", None))
        pack = attrs.get("pack", getattr(self.instance, "pack", None))

        if product and pack:
            raise serializers.ValidationError(
                "Une recette ne peut être liée qu'à un seul produit OU un "
                "seul pack, pas les deux à la fois."
            )
        return attrs

    def create(self, validated_data):
        try:
            return Recette.objects.create(**validated_data)
        except DjangoValidationError as exc:
            # Traduit une erreur de compression vidéo (levée dans Recette.save)
            # en erreur DRF propre, rattachée au champ "video".
            raise serializers.ValidationError({"video": exc.messages}) from exc

    def update(self, instance, validated_data):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        try:
            instance.save()
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"video": exc.messages}) from exc
        return instance

    def to_representation(self, instance):
        """Enrichit la sortie admin avec un aperçu simplifié du produit/pack lié."""
        representation = super().to_representation(instance)

        if instance.product:
            representation["product_detail"] = {
                "id": str(instance.product.id),
                "name": instance.product.name,
                "slug": instance.product.slug,
            }
        if instance.pack:
            representation["pack_detail"] = {
                "id": str(instance.pack.id),
                "name": instance.pack.name,
                "slug": instance.pack.slug,
            }
        return representation
