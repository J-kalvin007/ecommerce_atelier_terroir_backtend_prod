from django_filters.rest_framework import (
    CharFilter,
    FilterSet,
)

from .models import Recette


class RecetteFilter(FilterSet):
    """
    Permet de récupérer les recettes d'un produit ou d'un pack particulier,
    par identifiant ou par slug.
    """

    slug = CharFilter(
        field_name="slug",
        help_text="Slug de la recette.",
    )

    product = CharFilter(
        field_name="product_id",
        help_text="Identifiant du produit dont on veut les recettes.",
    )

    product_slug = CharFilter(
        field_name="product__slug",
        help_text="Slug du produit dont on veut les recettes.",
    )

    pack = CharFilter(
        field_name="pack_id",
        help_text="Identifiant du pack dont on veut les recettes.",
    )

    pack_slug = CharFilter(
        field_name="pack__slug",
        help_text="Slug du pack dont on veut les recettes.",
    )

    class Meta:
        model = Recette

        fields = [
            "product",
            "pack",
        ]
