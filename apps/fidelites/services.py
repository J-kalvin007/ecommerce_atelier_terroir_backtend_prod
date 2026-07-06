"""
Couche de services métier pour le module de fidélisation.

LoyaltyService orchestre :
- L'attribution de points après livraison
- Le cashback automatique (crédit wallet)
- La dépense de points
- L'expiration des points
- Les bonus (parrainage, anniversaire)
"""
import logging
import datetime
from decimal import Decimal
from typing import Optional

from django.conf import settings
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from .models import LoyaltyTier, LoyaltyProfile, LoyaltyEvent

logger = logging.getLogger(__name__)

# ─── Constantes (configurables dans settings) ────────────────────────────
POINT_VALUE = Decimal(getattr(settings, "LOYALTY_POINT_VALUE", "100.00"))
POINTS_EXPIRY_DAYS = getattr(settings, "LOYALTY_POINTS_EXPIRY_DAYS", 365)
REFERRAL_BONUS_POINTS = getattr(settings, "LOYALTY_REFERRAL_BONUS_POINTS", 200)
BIRTHDAY_BONUS_POINTS = getattr(settings, "LOYALTY_BIRTHDAY_BONUS_POINTS", 500)
FIRST_PURCHASE_BONUS_POINTS = getattr(settings, "LOYALTY_FIRST_PURCHASE_BONUS_POINTS", 100)


class LoyaltyService:
    """
    Moteur de fidélisation : points, cashback, paliers.

    Toutes les opérations financières (cashback) passent par WalletService
    pour garantir la cohérence du journal WalletTransaction.
    """

    @staticmethod
    @transaction.atomic
    def award_points(user, order) -> Optional[LoyaltyEvent]:
        """
        Attribue des points de fidélité après une commande livrée.

        Calcule les points de base (total commande),
        ajoute un bonus premier achat si applicable.

        IDEMPOTENCE : vérifie si un LoyaltyEvent reason=PURCHASE existe
        déjà pour cette commande avant tout traitement.

        Args:
            user: Utilisateur propriétaire de la commande.
            order: Commande livrée (Order instance).

        Returns:
            LoyaltyEvent créé, ou None si déjà traité.
        """
        # Anti-double-traitement
        if LoyaltyEvent.objects.filter(
            user=user, order=order, reason=LoyaltyEvent.Reason.PURCHASE
        ).exists():
            logger.info(
                "Points déjà attribués pour la commande %s — ignoré.",
                order.reference,
            )
            return None

        from .models import PointValue, LoyaltyRewardRule
        point_config = PointValue.objects.filter(is_active=True).first()
        validity_days = point_config.duree_validite if point_config else getattr(settings, "LOYALTY_POINTS_EXPIRY_DAYS", 365)

        profile = LoyaltyProfile.objects.select_for_update().get(user=user)

        # Points de base selon les règles de bénéfice
        rule = LoyaltyRewardRule.objects.filter(
            is_active=True,
            montant_min__lte=order.total_final,
            montant_max__gte=order.total_final,
        ).order_by("-level").first()

        base_points = rule.nombre_point_gagner if rule else 0
        points_awarded = base_points

        events_created = []

        # Bonus premier achat
        is_first_order = not LoyaltyEvent.objects.filter(
            user=user, reason=LoyaltyEvent.Reason.PURCHASE
        ).exists()
        
        if is_first_order:
            points_awarded += FIRST_PURCHASE_BONUS_POINTS
            events_created.append(
                LoyaltyEvent.objects.create(
                    user=user,
                    points_delta=FIRST_PURCHASE_BONUS_POINTS,
                    new_points_balance_after=profile.points_balance + FIRST_PURCHASE_BONUS_POINTS,
                    reason=LoyaltyEvent.Reason.FIRST_PURCHASE,
                    order=order,
                    description=f"Bonus premier achat : +{FIRST_PURCHASE_BONUS_POINTS} pts",
                )
            )

        if points_awarded == 0:
            logger.info("Aucun point à attribuer pour la commande %s selon les règles.", order.reference)
            return None

        # Mettre à jour le profil
        profile.points_balance = F("points_balance") + points_awarded
        profile.total_points_gagne = F("total_points_gagne") + points_awarded
        profile.total_solde = F("total_solde") + order.total_final
        profile.save(update_fields=["points_balance", "total_points_gagne", "total_solde", "updated_at"])
        profile.refresh_from_db()

        # Event principal d'achat
        event = LoyaltyEvent.objects.create(
            user=user,
            points_delta=base_points,
            new_points_balance_after=profile.points_balance,
            reason=LoyaltyEvent.Reason.PURCHASE,
            order=order,
            expires_at=timezone.now() + datetime.timedelta(days=validity_days),
            description=f"Points gagnés sur commande {order.reference}",
        )

        # Recalculer le palier
        profile.recalculate_tier()

        logger.info(
            "Points attribués à %s : +%d pts (total: %d)",
            user.email,
            points_awarded,
            profile.points_balance,
        )
        return event



    @staticmethod
    @transaction.atomic
    def redeem_points(user, order, points_to_spend: int) -> Decimal:
        """
        Dépense des points de fidélité pour obtenir une réduction.

        Utilise select_for_update() sur le profil pour éviter les
        soldes négatifs en cas de requêtes concurrentes.

        Args:
            user: Utilisateur.
            order: Commande en cours.
            points_to_spend: Nombre de points à dépenser.

        Returns:
            Decimal: Montant de réduction obtenu.

        Raises:
            ValueError: Si points_to_spend > points_balance.
        """
        profile = LoyaltyProfile.objects.select_for_update().get(user=user)

        if points_to_spend <= 0:
            raise ValueError("Le nombre de points doit être positif.")

        if points_to_spend > profile.points_balance:
            raise ValueError(
                f"Solde insuffisant. Vous avez {profile.points_balance} pts, "
                f"vous demandez {points_to_spend} pts."
            )

        # Calculer la réduction
        from .models import PointValue
        point_config = PointValue.objects.filter(is_active=True).first()
        
        if point_config and point_config.nombre_de_point > 0:
            point_value_ratio = point_config.valeur_un_point_frcfa / Decimal(point_config.nombre_de_point)
            discount = (Decimal(points_to_spend) * point_value_ratio).quantize(Decimal("0.01"))
        else:
            POINT_VALUE_SETTING = Decimal(getattr(settings, "LOYALTY_POINT_VALUE", "100.00"))
            discount = (Decimal(points_to_spend) * POINT_VALUE_SETTING / Decimal("100.00")).quantize(Decimal("0.01"))

        # Décrémenter le solde
        profile.points_balance = F("points_balance") - points_to_spend
        profile.save(update_fields=["points_balance", "updated_at"])
        profile.refresh_from_db()

        # Créer l'événement
        LoyaltyEvent.objects.create(
            user=user,
            points_delta=-points_to_spend,
            new_points_balance_after=profile.points_balance,
            reason=LoyaltyEvent.Reason.ORDER_DISCOUNT,
            order=order,
            description=f"Dépense {points_to_spend} pts → réduction {discount} FCFA",
        )

        # Appliquer la réduction à la commande
        order.discount_amount = F("discount_amount") + discount
        order.total_final = F("total_final") - discount
        order.save(update_fields=["discount_amount", "total_final", "updated_at"])
        order.refresh_from_db()

        logger.info(
            "Points dépensés par %s : -%d pts → -%s FCFA",
            user.email,
            points_to_spend,
            discount,
        )
        return discount

    @staticmethod
    def expire_points():
        """
        Tâche planifiée : expire les points dont la date est dépassée.

        Pour chaque LoyaltyEvent reason=PURCHASE expiré et non déjà
        traité (points_delta > 0), crée un événement POINTS_EXPIRY
        et décrémente le solde.
        """
        from django.db.models import Sum

        now = timezone.now()
        expired_events = LoyaltyEvent.objects.filter(
            reason=LoyaltyEvent.Reason.PURCHASE,
            points_delta__gt=0,
            expires_at__isnull=False,
            expires_at__lt=now,
        )

        processed = 0
        for event in expired_events:
            with transaction.atomic():
                profile = LoyaltyProfile.objects.select_for_update().get(
                    user=event.user
                )
                # Vérifier que le solde est suffisant
                expire_amount = min(event.points_delta, profile.points_balance)
                if expire_amount <= 0:
                    continue

                profile.points_balance = F("points_balance") - expire_amount
                profile.save(update_fields=["points_balance", "updated_at"])
                profile.refresh_from_db()

                LoyaltyEvent.objects.create(
                    user=event.user,
                    points_delta=-expire_amount,
                    new_points_balance_after=profile.points_balance,
                    reason=LoyaltyEvent.Reason.POINTS_EXPIRY,
                    description=f"Expiration de {expire_amount} pts (commande du {event.created_at.date()})",
                )
                processed += 1

        logger.info("Expiration de points terminée : %d événements traités.", processed)
        return processed
