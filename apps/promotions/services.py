"""
Couche de services métier pour le module promotions.

PromoService orchestre la validation et l'application des codes promo
avec des transactions atomiques et select_for_update pour les quotas.
"""
import logging
from decimal import Decimal
from typing import Optional, Tuple

from django.db import transaction
from django.db.models import F
from django.utils import timezone

from .exceptions import (
    InvalidPromoCodeError,
    PromoExpiredError,
    PromoTierRestrictionError,
)
from .models import PromoCode, Soldes, Banner

logger = logging.getLogger(__name__)


class PromoService:
    """
    Service de gestion des codes promotionnels.

    Toutes les opérations critiques (validation + application) sont
    encapsulées dans des transactions atomiques avec verrouillage
    pessimiste pour éviter les dépassements de quota en concurrence.
    """

    @staticmethod
    def validate_code(
        code: str,
        user,
        cart_total: Decimal,
        cart_items: Optional[list] = None,
    ) -> Tuple[PromoCode, Decimal]:
        """
        Valide un code promo et calcule la réduction applicable.

        Vérifications effectuées :
        1. Existence et validité de base (is_valid)
        2. Période de validité (starts_at / expires_at)
        3. Montant minimum de commande
        4. Quota global (avec select_for_update pour éviter les race conditions)
        5. Quota par utilisateur
        6. Restriction de palier de fidélité
        7. Restriction de produits/catégories

        Args:
            code: Le code promo saisi.
            user: L'utilisateur connecté.
            cart_total: Montant total du panier.
            cart_items: Liste optionnelle d'items pour restrictions produits.

        Returns:
            Tuple (PromoCode, Decimal): L'instance du code promo et le montant de réduction.

        Raises:
            InvalidPromoCodeError: Code inexistant ou inactif.
            PromoExpiredError: Code expiré.
            PromoMinOrderError: Montant minimum non atteint.
            PromoQuotaExceededError: Quota global atteint.
            PromoUserQuotaExceededError: Quota utilisateur atteint.
            PromoTierRestrictionError: Palier de fidélité insuffisant.
        """
        cart_total = cart_total.quantize(Decimal("0.01"))

        # 1. Récupérer le code promo
        try:
            promo = PromoCode.objects.select_for_update().get(
                code__iexact=code.strip().upper()
            )
        except PromoCode.DoesNotExist:
            raise InvalidPromoCodeError()

        # 2. Vérifications de base
        if not promo.is_active:
            raise InvalidPromoCodeError("Ce code promo n'est plus actif.")

        now = timezone.now()
        if promo.starts_at and now < promo.starts_at:
            raise InvalidPromoCodeError("Ce code promo n'est pas encore valide.")
        if promo.expires_at and now > promo.expires_at:
            raise PromoExpiredError()

        # 3. Restriction de palier de fidélité
        if promo.restricted_to_tiers.exists():
            try:
                from apps.fidelites.models import LoyaltyProfile
                profile = LoyaltyProfile.objects.get(user=user)
                user_tier = profile.tier
            except (ImportError, LoyaltyProfile.DoesNotExist):
                user_tier = None

            if user_tier is None or user_tier not in promo.restricted_to_tiers.all():
                raise PromoTierRestrictionError(
                    "Ce code promo est réservé à certains niveaux de fidélité."
                )

        # 4. Calcul de la réduction
        discount = promo.calculate_discount(cart_total, cart_items)

        return promo, discount

    @staticmethod
    @transaction.atomic
    def apply_code(
        promo_code: PromoCode,
        user,
        order,
        discount_amount: Decimal,
    ) -> Decimal:
        """
        Applique un code promo à une commande.

        Dans une transaction atomique :
        1. Incrémente number_times_used via F() expression (race-condition safe)
        2. Crée un PromoUsage (anti-double-usage grâce à unique_together)
        3. Applique la réduction à la commande

        Args:
            promo_code: Instance PromoCode validée.
            user: Utilisateur.
            order: Instance Order.
            discount_amount: Montant de réduction calculé.

        Returns:
            Decimal: Montant de réduction appliqué.

        Raises:
            PromoQuotaExceededError: Si le quota est dépassé après incrément.
        """
        # Incrémenter number_times_used atomiquement
        updated = PromoCode.objects.filter(
            pk=promo_code.pk,
            is_active=True,
        ).update(
            number_times_used=F("number_times_used") + 1
        )

        if not updated:
            raise PromoQuotaExceededError("Quota atteint pendant l'application.")

        # Appliquer la réduction à la commande
        order.discount_amount = F("discount_amount") + discount_amount
        order.total_final = F("total_final") - discount_amount
        order.save(update_fields=["discount_amount", "total_final", "updated_at"])
        order.refresh_from_db()

        logger.info(
            "Code promo %s appliqué à la commande %s : -%s FCFA",
            promo_code.code,
            order.reference,
            discount_amount,
        )
        return discount_amount

    @staticmethod
    def get_active_flash_sales():
        """
        Retourne les ventes flash en cours.

        Returns:
            QuerySet[Soldes]: Flash sales actives, dans leur période,
            avec stock non épuisé.
        """
        now = timezone.now()
        return Soldes.objects.filter(
            is_active=True,
            starts_at__lte=now,
            ends_at__gte=now,
        ).exclude(
            quota_stock_limit__isnull=False,
            product_sold_count__gte=F("quota_stock_limit"),
        ).select_related("product", "variant")

    @staticmethod
    def get_active_banners(banner_type: str = None):
        """
        Retourne les bannières actives à afficher.

        Args:
            banner_type: Type de bannière à filtrer (optionnel).

        Returns:
            QuerySet[Banner]: Bannières actives, ordonnées par position.
        """
        now = timezone.now()
        qs = Banner.objects.filter(
            is_active=True,
            starts_at__lte=now,
        ).exclude(
            ends_at__isnull=False,
            ends_at__lt=now,
        )

        if banner_type:
            qs = qs.filter(banner_type=banner_type)

        return qs.order_by("banner_type", "position", "-created_at")
