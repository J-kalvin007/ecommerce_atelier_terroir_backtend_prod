"""
Modèles du module de fidélisation.

Architecture :
- LoyaltyTier      : paliers VIP avec avantages progressifs (Bronze → Elite)
- LoyaltyProfile   : profil de fidélité par utilisateur (1-to-1)
- LoyaltyEvent     : journal immuable de tous les mouvements de points
- TierChangeLog    : audit trail des changements de palier

Principes de conception :
- points_balance est protégé par une CheckConstraint ≥ 0 au niveau BDD
- Toutes les opérations de débit utilisent select_for_update() (dans les services)
- total_points_gagne est un compteur lifetime, jamais décrémenté
- total_solde cumule les dépenses sur commandes livrées
"""
from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models

from apps.core.models import BaseModel


# ─────────────────────────────────────────────────────────────────────────────
# LOYALTY TIER
# ─────────────────────────────────────────────────────────────────────────────

class LoyaltyTier(BaseModel):
    """
    Palier de fidélité (VIP).

    Définit les seuils et avantages pour chaque niveau.
    Le critère d'éligibilité repose uniquement sur les points cumulés (total_points_gagne).

    Attributs :
        name            : Nom du palier (Bronze, Silver, Gold…)
        min_points      : Points cumulés minimum requis pour ce palier
        min_solde       : Dépenses totales minimum en FCFA (information complémentaire)
        discount_percent: Réduction automatique sur les commandes (%)
    """

    name = models.CharField(
        max_length=50,
        unique=True,
        help_text="Nom du palier (Bronze, Silver, Gold…).",
    )

    min_points = models.PositiveIntegerField(
        default=0,
        help_text="Points cumulés (lifetime) minimum requis pour accéder à ce palier.",
    )

    min_solde = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Dépenses totales minimum (FCFA) — critère informatif.",
    )

    discount_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text="Réduction automatique appliquée sur les commandes (%).",
    )


    class Meta:
        db_table = "loyalty_tiers"
        verbose_name = "Palier de fidélité"
        verbose_name_plural = "Paliers de fidélité"
        ordering = ["min_points"]

    def __str__(self):
        return f"{self.name} (≥ {self.min_points} pts)"


# ─────────────────────────────────────────────────────────────────────────────
# LOYALTY PROFILE
# ─────────────────────────────────────────────────────────────────────────────

class LoyaltyProfile(BaseModel):
    """
    Profil de fidélité personnel d'un utilisateur (relation 1-to-1).

    Stocke :
    - Le solde de points disponibles (points_balance)
    - Le total de points gagnés lifetime (total_points_gagne, jamais décrémenté)
    - Les dépenses cumulées sur commandes livrées (total_solde)
    - Le palier actuel (tier → LoyaltyTier)

    Contraintes :
    - points_balance ≥ 0 (CheckConstraint BDD)
    - Les débits DOIVENT passer par select_for_update() dans les services
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="loyalty_profile",
        help_text="Utilisateur propriétaire de ce profil.",
    )

    tier = models.ForeignKey(
        LoyaltyTier,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="profiles",
        help_text="Palier actuel. Assigné automatiquement à la création puis recalculé.",
    )

    points_balance = models.PositiveIntegerField(
        default=0,
        help_text="Solde de points disponibles pour dépense ou expiration.",
    )

    total_points_gagne = models.PositiveIntegerField(
        default=0,
        help_text="Total de points gagnés (lifetime). Jamais décrémenté. Sert au calcul de palier.",
    )

    total_points_earned = models.PositiveIntegerField(
        default=0,
        help_text="Total de points gagnés (lifetime). Jamais décrémenté. Sert au calcul de palier.",
    )

    total_solde = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Dépenses cumulées sur commandes livrées (FCFA).",
    )


    class Meta:
        db_table = "loyalty_profiles"
        verbose_name = "Profil de fidélité"
        verbose_name_plural = "Profils de fidélité"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(points_balance__gte=0),
                name="loyalty_points_balance_non_negative",
            )
        ]
        indexes = [
            models.Index(fields=["tier"]),
        ]

    def __str__(self):
        tier_name = self.tier.name if self.tier else "Aucun palier"
        return f"Loyalty {self.user.email} — {tier_name} ({self.points_balance} pts)"

    def recalculate_tier(self) -> bool:
        """
        Recalcule le palier en fonction des points cumulés (total_points_gagne).

        Parcourt les paliers du plus élevé au plus bas et sélectionne
        le premier pour lequel l'utilisateur est éligible selon son total_points_gagne.

        Returns:
            bool: True si le palier a changé et été sauvegardé, False sinon.
        """
        old_tier = self.tier

        # Palier éligible = le plus haut dont on a atteint le seuil de points
        new_tier = (
            LoyaltyTier.objects.filter(
                is_active=True,
                min_points__lte=self.total_points_gagne,
            )
            .order_by("-min_points")
            .first()
        )

        if new_tier and new_tier != old_tier:
            self.tier = new_tier
            self.save(update_fields=["tier", "updated_at"])

            # Audit trail du changement de palier
            TierChangeLog.objects.create(
                user=self.user,
                from_tier=old_tier.name if old_tier else "Aucun",
                to_tier=new_tier.name,
                reason=(
                    f"Recalcul automatique : "
                    f"{self.total_points_gagne} pts cumulés, "
                    f"{self.total_solde} FCFA dépensés."
                ),
            )
            return True
        return False


# ─────────────────────────────────────────────────────────────────────────────
# LOYALTY EVENT
# ─────────────────────────────────────────────────────────────────────────────

class LoyaltyEvent(BaseModel):
    """
    Journal immuable de tous les mouvements de points de fidélité.

    Chaque ligne représente un événement atomique :
    gain (points_delta > 0), dépense ou expiration (points_delta ≤ 0).

    Le champ new_points_balance_after est un snapshot du solde APRÈS
    le mouvement — permet un audit complet sans recalcul.

    Note : les LoyaltyEvent sont en lecture seule une fois créés.
    Aucune méthode de mise à jour ne doit être appelée sur ces instances.
    """

    class Reason(models.TextChoices):
        PURCHASE           = "purchase",          "Achat"
        REFUND             = "refund",             "Remboursement"
        # REFERRAL_BONUS     = "referral_bonus",     "Bonus parrainage"
        FIRST_PURCHASE     = "first_purchase",     "Premier achat"
        BIRTHDAY_BONUS     = "birthday_bonus",     "Bonus anniversaire"
        POINTS_EXPIRY      = "points_expiry",      "Expiration de points"
        ADMIN_ADJUSTMENT   = "admin_adjustment",   "Ajustement administrateur"
        ORDER_DISCOUNT     = "order_discount",     "Réduction commande"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="loyalty_events",
        help_text="Utilisateur concerné par cet événement.",
    )

    points_delta = models.IntegerField(
        help_text="Variation de points : positif = gain, négatif = dépense/expiration.",
    )

    new_points_balance_after = models.PositiveIntegerField(
        help_text="Snapshot du solde de points immédiatement après ce mouvement.",
    )

    reason = models.CharField(
        max_length=30,
        choices=Reason.choices,
        db_index=True,
        help_text="Catégorie de l'événement.",
    )

    order = models.ForeignKey(
        "commandes.Order",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="loyalty_events",
        help_text="Commande associée (si applicable).",
    )

    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Date d'expiration des points gagnés (uniquement pour les gains PURCHASE).",
    )

    description = models.TextField(
        blank=True,
        help_text="Description lisible de l'événement pour l'historique client.",
    )

    class Meta:
        db_table = "loyalty_events"
        verbose_name = "Événement de fidélité"
        verbose_name_plural = "Événements de fidélité"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["reason"]),
            models.Index(fields=["expires_at"]),
            models.Index(fields=["order"]),
        ]

    def __str__(self):
        sign = "+" if self.points_delta >= 0 else ""
        return (
            f"{self.user.email} : {sign}{self.points_delta} pts "
            f"({self.get_reason_display()}) → solde : {self.new_points_balance_after} pts"
        )


# ─────────────────────────────────────────────────────────────────────────────
# TIER CHANGE LOG
# ─────────────────────────────────────────────────────────────────────────────

# class TierChangeLog(BaseModel):
#     """
#     Audit trail des changements de palier de fidélité.

#     Enregistre automatiquement chaque montée ou descente de palier
#     avec la raison et les paliers source/destination.
#     Permet un suivi complet de l'évolution du statut VIP de chaque client.
#     """

#     user = models.ForeignKey(
#         settings.AUTH_USER_MODEL,
#         on_delete=models.CASCADE,
#         related_name="tier_changes",
#         help_text="Utilisateur dont le palier a changé.",
#     )

#     from_tier = models.CharField(
#         max_length=50,
#         blank=True,
#         help_text="Nom du palier précédent (vide si premier palier).",
#     )

#     to_tier = models.CharField(
#         max_length=50,
#         help_text="Nom du nouveau palier.",
#     )

#     reason = models.TextField(
#         blank=True,
#         help_text="Explication du changement (points, dépenses, ajustement admin…).",
#     )

#     class Meta:
#         db_table = "loyalty_tier_change_logs"
#         verbose_name = "Changement de palier"
#         verbose_name_plural = "Changements de palier"
#         ordering = ["-created_at"]

#     def __str__(self):
#         return f"{self.user.email} : {self.from_tier or 'Aucun'} → {self.to_tier}"


# ─────────────────────────────────────────────────────────────────────────────
# VALEUR DES POINTS & RÈGLES DE GAIN
# ─────────────────────────────────────────────────────────────────────────────

class PointValue(BaseModel):
    """
    Configuration globale de la valeur des points de fidélité.
    
    Cette table est unique (gérée par la logique métier) et définit :
    - La valeur d'un certain nombre de points en FCFA.
    - Le nombre de points correspondant à cette valeur.
    - La durée de validité des points gagnés (en jours).
    
    Exposée via l'API publique pour affichage sur le front.
    """
    
    valeur_un_point_frcfa = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Valeur correspondante en FCFA.",
    )
    
    nombre_de_point = models.PositiveIntegerField(
        help_text="Quantité de points (ex: 1).",
    )
    
    duree_validite = models.PositiveIntegerField(
        default=365,
        help_text="Durée de validité des points gagnés (en jours).",
    )
    
    is_active = models.BooleanField(
        default=True,
        help_text="Marquer comme configuration active (une seule recommandée).",
    )

    class Meta:
        db_table = "loyalty_point_values"
        verbose_name = "Valeur des points"
        verbose_name_plural = "Valeurs des points"

    def __str__(self):
        return f"{self.nombre_de_point} pts = {self.valeur_un_point_frcfa} FCFA (Validité: {self.duree_validite}j)"


class LoyaltyRewardRule(BaseModel):
    """
    Règle de gain de points (Bénéfice).
    
    Définit combien de points un utilisateur gagne si sa commande 
    se situe dans une tranche de montant [montant_min, montant_max].
    Réservé à l'administration.
    """
    
    level = models.PositiveIntegerField(
        help_text="Niveau de la règle (ex: 1, 2, 3...) pour l'ordre d'affichage ou de priorité.",
    )
    
    montant_min = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="Montant minimum d'achat (inclus).",
    )
    
    montant_max = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="Montant maximum d'achat (inclus).",
    )
    
    nombre_point_gagner = models.PositiveIntegerField(
        help_text="Nombre de points fixes gagnés pour cette tranche d'achat.",
    )
    
    is_active = models.BooleanField(
        default=True,
        help_text="Règle active ou non.",
    )

    class Meta:
        db_table = "loyalty_reward_rules"
        verbose_name = "Règle de gain (Bénéfice)"
        verbose_name_plural = "Règles de gain (Bénéfices)"
        ordering = ["montant_min"]
        
    def __str__(self):
        return f"Niveau {self.level} : {self.montant_min} à {self.montant_max} FCFA -> +{self.nombre_point_gagner} pts"
