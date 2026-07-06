"""
Signaux Django pour le module de fidélisation.

- post_save Order : attribue points et cashback quand le statut passe à DELIVERED
- post_save User : crée automatiquement un LoyaltyProfile avec tier par défaut

PROTECTION ANTI-DOUBLE-DÉCLENCHEMENT :
- Vérification d'un LoyaltyEvent existant pour cet order avant tout traitement
- Utilisation d'un flag _loyalty_processed sur l'instance Order
"""
import logging

from django.conf import settings
from django.db import transaction, models
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import LoyaltyProfile, LoyaltyEvent
from .services import LoyaltyService

logger = logging.getLogger(__name__)


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_loyalty_profile(sender, instance, created, **kwargs):
    """
    Crée automatiquement un LoyaltyProfile à la création d'un utilisateur.

    Le profil est initialisé avec le palier par défaut (is_default=True)
    et un code de parrainage unique.
    """
    if created and not hasattr(instance, "loyalty_profile"):
        LoyaltyProfile.objects.create(user=instance)
        logger.info("LoyaltyProfile créé pour %s", instance.email)


@receiver(post_save, sender="commandes.Order")
def handle_order_status_change(sender, instance, **kwargs):
    """
    Traite les changements de statut de commande pour la fidélité.

    - DELIVERED → award_points() + award_cashback()
    - REFUNDED  → annuler les points (log uniquement pour le cashback)

    IDEMPOTENCE : vérifie l'existence d'un LoyaltyEvent reason=PURCHASE
    avant tout traitement pour éviter les doubles attributions.
    """
    # Éviter la récursion infinie si on save() dans ce handler
    if getattr(instance, "_loyalty_processing", False):
        return

    try:
        instance._loyalty_processing = True

        if instance.status == "delivered":
            # Vérification d'idempotence
            if not LoyaltyEvent.objects.filter(
                user=instance.user,
                order=instance,
                reason=LoyaltyEvent.Reason.PURCHASE,
                points_delta__gt=0,
            ).exists():
                logger.info(
                    "Commande %s livrée → attribution points pour %s",
                    instance.reference,
                    instance.user.email,
                )
                LoyaltyService.award_points(user=instance.user, order=instance)
            else:
                logger.info(
                    "Commande %s déjà traitée pour la fidélité — ignoré.",
                    instance.reference,
                )

        elif instance.status == "refunded":
            # Annuler les points (créer un événement négatif)
            if not LoyaltyEvent.objects.filter(
                user=instance.user,
                order=instance,
                reason=LoyaltyEvent.Reason.REFUND,
            ).exists():
                # Récupérer les points attribués pour cette commande
                purchase_event = LoyaltyEvent.objects.filter(
                    user=instance.user,
                    order=instance,
                    reason=LoyaltyEvent.Reason.PURCHASE,
                    points_delta__gt=0,
                ).first()

                if purchase_event:
                    with transaction.atomic():
                        profile = LoyaltyProfile.objects.select_for_update().get(
                            user=instance.user
                        )
                        refund_points = min(
                            purchase_event.points_delta, profile.points_balance
                        )
                        if refund_points > 0:
                            profile.points_balance = (
                                models.F("points_balance") - refund_points
                            )
                            profile.save(
                                update_fields=["points_balance", "updated_at"]
                            )
                            profile.refresh_from_db()

                            LoyaltyEvent.objects.create(
                                user=instance.user,
                                points_delta=-refund_points,
                                new_points_balance_after=profile.points_balance,
                                reason=LoyaltyEvent.Reason.REFUND,
                                order=instance,
                                description=f"Remboursement commande {instance.reference} : -{refund_points} pts",
                            )
                            logger.info(
                                "Points annulés pour commande %s : -%d pts",
                                instance.reference,
                                refund_points,
                            )
    finally:
        instance._loyalty_processing = False