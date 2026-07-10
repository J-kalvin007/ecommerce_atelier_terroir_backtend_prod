"""
Service de recommandations de produits — Atelier du Terroir.

Stratégie :
  1. Utilisateur avec commandes :
     → Catégorie du produit le plus commandé (via OrderItem → ProductVariant → Product)
     → Top 5 produits actifs de cette catégorie (triés par note + order_count)

  2. Utilisateur sans commandes / anonyme :
     → Score composite sur l'ensemble du catalogue :
       score = (order_count × 0.5) + (count_favorites × 0.3) + (note_produit × 20 × 0.2)
     → Top 6 produits retournés

@module apps.chatbot.recommendation_service
"""
import logging
from decimal import Decimal

logger = logging.getLogger(__name__)


class RecommendationService:
    """
    Génère des recommandations de produits personnalisées via requêtes ORM.

    Aucun appel LLM — les recommandations sont entièrement calculées en Python/SQL
    pour minimiser la latence et les coûts.

    Args:
        user: Instance User authentifiée, ou None pour un anonyme.
        products_payload: Liste de dicts {id, name, category, price} fournie par le frontend
                          (catalogue actuellement visible côté client).
    """

    MAX_RECOMMENDATIONS = 6

    def __init__(self, user=None, products_payload: list[dict] | None = None, viewed_categories: list[str] | None = None, user_intent: str = "") -> None:
        self.user = user
        self.products_payload = products_payload or []
        self.viewed_categories = viewed_categories or []
        self.user_intent = user_intent

    # =========================================================================
    #  POINT D'ENTRÉE
    # =========================================================================

    def get_recommendations(self) -> list[dict]:
        """
        Retourne une liste ordonnée de recommandations.

        Returns:
            Liste de dicts avec :
                - product_id  : str (UUID du produit)
                - reason      : str (justification en français)
                - score       : float (score composite)
        """
        from apps.catalog.models import Product

        if self.viewed_categories or self.user_intent:
            # Contexte présent (utilisateur regarde un produit spécifique)
            return self._contextual_recommendations()
        elif self.user and not getattr(self.user, "is_anonymous", True):
            # Utilisateur connecté → recommandations personnalisées
            return self._personalized_recommendations()
        else:
            # Anonyme → recommandations populaires
            return self._popular_recommendations()

    def _format_product(self, p) -> dict:
        """Formate le produit pour le frontend sans serializer complet."""
        primary = p.images.filter(is_primary=True).first()
        return {
            "id": str(p.id),
            "name": p.name,
            "slug": p.slug,
            "price": float(p.price) if p.price else 0.0,
            "category": p.category.name if p.category else None,
            "primary_image": primary.image.url if primary and primary.image else None,
        }

    # =========================================================================
    #  RECOMMANDATIONS CONTEXTUELLES (page produit en cours)
    # =========================================================================

    def _contextual_recommendations(self) -> list[dict]:
        """
        Recommandations basées sur le produit ou la catégorie actuellement consultés.
        Privilégie les produits de la même catégorie.
        """
        from apps.catalog.models import Product

        # Extraire le nom du produit consulté depuis l'intention si présent
        # Ex: "Je regarde le produit Viande Hachée Bio"
        viewed_product_name = ""
        if "Je regarde le produit " in self.user_intent:
            viewed_product_name = self.user_intent.split("Je regarde le produit ")[-1].strip()

        qs = Product.objects.filter(is_active=True, stock__gt=0).select_related("category")
        
        # Exclure le produit actuellement consulté
        if viewed_product_name:
            qs = qs.exclude(name__iexact=viewed_product_name)
            
        candidates = []
        
        # Essayer de trouver des produits dans les catégories vues
        if self.viewed_categories:
            cat_qs = qs.filter(category__name__in=self.viewed_categories)
            # Trier par popularité
            cat_candidates = list(cat_qs.only(
                "id", "name", "slug", "price", "category",
                "order_count", "count_favorites", "note_produit",
                "is_top", "count_ratings",
            ))
            cat_candidates.sort(key=self._compute_score, reverse=True)
            candidates.extend(cat_candidates[:self.MAX_RECOMMENDATIONS])
            
        # Si on n'a pas assez de recommandations contextuelles, on complète avec les populaires
        if len(candidates) < self.MAX_RECOMMENDATIONS:
            excluded_ids = [c.id for c in candidates]
            if viewed_product_name:
                # Filtrer le nom sur la db pour l'exclusion de sécurité
                pass
                
            pop_qs = qs.exclude(id__in=excluded_ids)
            pop_candidates = list(pop_qs.only(
                "id", "name", "slug", "price", "category",
                "order_count", "count_favorites", "note_produit",
                "is_top", "count_ratings",
            ))
            pop_candidates.sort(key=self._compute_score, reverse=True)
            candidates.extend(pop_candidates[:(self.MAX_RECOMMENDATIONS - len(candidates))])

        results = []
        for p in candidates:
            is_contextual = self.viewed_categories and p.category and p.category.name in self.viewed_categories
            reason = (
                f"Suggéré car vous consultez la catégorie {p.category.name}."
                if is_contextual else "Très apprécié par nos clients."
            )
            results.append({
                "product": self._format_product(p),
                "reason": reason,
                "score": round(self._compute_score(p), 4),
            })
            
        return results

    # =========================================================================
    #  RECOMMANDATIONS PERSONNALISÉES
    # =========================================================================

    def _personalized_recommendations(self) -> list[dict]:
        """
        Recommandations basées sur l'historique d'achat de l'utilisateur.

        Stratégie :
        1. Trouver le produit le plus commandé par l'utilisateur
        2. Prendre sa catégorie
        3. Retourner les meilleurs produits de cette catégorie (hors ceux déjà commandés)
        """
        from apps.commandes.models import OrderItem
        from apps.catalog.models import Product

        # Produits déjà commandés par l'utilisateur
        ordered_variant_ids = list(
            OrderItem.objects.filter(order__user=self.user)
            .values_list("product_id", flat=True)
            .distinct()
        )

        if not ordered_variant_ids:
            # Pas encore de commandes → fallback sur les produits populaires
            return self._popular_recommendations(reason_prefix="Tendance sur la plateforme")

        # Import Sum here to avoid circular issues
        from django.db.models import Sum

        # Produit le plus fréquemment commandé
        most_ordered = (
            OrderItem.objects.filter(order__user=self.user)
            .values("product_id")
            .annotate(total_qty=Sum("quantity"))
            .order_by("-total_qty")
            .first()
        )

        if not most_ordered:
            return self._popular_recommendations()

        # Retrouver le Product via la ProductVariant
        try:
            from apps.catalog.models import ProductVariant
            variant = ProductVariant.objects.select_related("product__category").get(
                pk=most_ordered["product_id"]
            )
            target_category = variant.product.category
            most_ordered_product_name = variant.product.name
        except Exception:
            return self._popular_recommendations()

        # Produits de la même catégorie, non encore commandés
        already_ordered_product_ids = list(
            ProductVariant.objects.filter(
                id__in=ordered_variant_ids,
            ).values_list("product_id", flat=True).distinct()
        )

        candidates = (
            Product.objects.filter(
                is_active=True,
                category=target_category,
            )
            .exclude(id__in=already_ordered_product_ids)
            .order_by("-note_produit", "-order_count", "-count_favorites")
        )[: self.MAX_RECOMMENDATIONS]

        if not candidates:
            # Même catégorie mais tout a déjà été commandé → produits similaires de toutes catégories
            candidates = (
                Product.objects.filter(is_active=True)
                .exclude(id__in=already_ordered_product_ids)
                .order_by("-note_produit", "-order_count", "-count_favorites")
            )[: self.MAX_RECOMMENDATIONS]

        return [
            {
                "product": self._format_product(p),
                "reason": (
                    f"Basé sur votre achat de {most_ordered_product_name}, "
                    f"vous aimerez sûrement ces produits de la catégorie {target_category.name}."
                ),
                "score": self._compute_score(p),
            }
            for p in candidates
        ]

    # =========================================================================
    #  RECOMMANDATIONS POPULAIRES (anonymes / sans historique)
    # =========================================================================

    def _popular_recommendations(self, reason_prefix: str = "Très apprécié par nos clients") -> list[dict]:
        """
        Retourne les produits les plus populaires sur la plateforme.

        Score composite : order_count × 0.5 + count_favorites × 0.3 + (note × 20) × 0.2
        """
        from apps.catalog.models import Product

        # Récupère tous les produits actifs avec les métriques de popularité
        products = list(
            Product.objects.filter(is_active=True, stock__gt=0)
            .select_related("category")
            .only(
                "id", "name", "slug", "price", "category",
                "order_count", "count_favorites", "note_produit",
                "is_top", "count_ratings",
            )
        )

        # Tri côté Python pour le score composite
        products.sort(key=self._compute_score, reverse=True)

        top = products[: self.MAX_RECOMMENDATIONS]

        return [
            {
                "product": self._format_product(p),
                "reason": f"{reason_prefix} — {p.order_count} commandes, {p.count_favorites} favoris, ⭐ {p.note_produit}/5",
                "score": round(self._compute_score(p), 4),
            }
            for p in top
        ]

    # =========================================================================
    #  UTILITAIRES
    # =========================================================================

    @staticmethod
    def _compute_score(product) -> float:
        """
        Score composite de popularité d'un produit.

        Formule :
            score = order_count × 0.5 + count_favorites × 0.3 + (note_produit × 20) × 0.2

        La note est multipliée par 20 pour la ramener sur une échelle comparable
        à order_count et count_favorites.
        """
        order_w = float(product.order_count or 0) * 0.5
        fav_w = float(product.count_favorites or 0) * 0.3
        note_w = float(product.note_produit or 0) * 20 * 0.2
        return order_w + fav_w + note_w

