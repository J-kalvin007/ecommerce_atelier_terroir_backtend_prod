"""
Couche de services métier pour le module recettes.

Centralise la construction des querysets de recettes, afin que la même
définition de "recette publiquement visible" soit partagée par la vue
publique et par tout autre point d'entrée (autre app, tâche, commande) qui
aurait besoin d'afficher des suggestions de recettes.
"""

from .models import Recette


class RecetteService:
    """Service regroupant la logique de récupération des recettes."""

    @staticmethod
    def get_active_recettes():
        """
        Retourne les recettes actives, avec leur produit/pack pré-chargé,
        triées des plus récentes aux plus anciennes.
        """
        return (
            Recette.objects
            .filter(is_active=True)
            .select_related("product", "pack")
            .order_by("-created_at")
        )

    @staticmethod
    def get_recettes_for_product(product_id):
        """Retourne les recettes actives liées à un produit donné."""
        return RecetteService.get_active_recettes().filter(product_id=product_id)

    @staticmethod
    def get_recettes_for_pack(pack_id):
        """Retourne les recettes actives liées à un pack de produits donné."""
        return RecetteService.get_active_recettes().filter(pack_id=pack_id)
