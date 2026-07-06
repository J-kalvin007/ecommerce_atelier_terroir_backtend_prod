from django.contrib import admin
from django.db import transaction
from django.db.models import F

from .models import LoyaltyTier, LoyaltyProfile, LoyaltyEvent, PointValue, LoyaltyRewardRule
from .services import LoyaltyService


@admin.register(LoyaltyTier)
class LoyaltyTierAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "min_points",
        "min_solde",
        "discount_percent",
    )
    list_editable = ("min_points",)
    ordering = ("min_points",)


@admin.register(LoyaltyProfile)
class LoyaltyProfileAdmin(admin.ModelAdmin):
    list_display = ("user_email", "tier", "points_balance", "total_points_gagne", "total_solde")
    list_filter = ("tier", "created_at")
    search_fields = ("user__email",)
    readonly_fields = ("total_points_gagne", "created_at", "updated_at")
    raw_id_fields = ("user",)
    actions = ["recalculate_tiers", "force_recalculate_single_tier"]

    def user_email(self, obj):
        return obj.user.email
    user_email.short_description = "Utilisateur"

    @admin.action(description="Recalculer les paliers sélectionnés")
    def recalculate_tiers(self, request, queryset):
        changed = 0
        for profile in queryset:
            if profile.recalculate_tier():
                changed += 1
        self.message_user(request, f"{changed} palier(s) mis à jour.")

    @admin.action(description="Forcer recalcul du palier (un seul)")
    def force_recalculate_single_tier(self, request, queryset):
        if queryset.count() != 1:
            self.message_user(request, "Sélectionnez un seul profil.", level="ERROR")
            return
        profile = queryset.first()
        if profile.recalculate_tier():
            self.message_user(request, f"Palier mis à jour : {profile.tier.name}")
        else:
            self.message_user(request, "Pas de changement de palier.")


@admin.register(LoyaltyEvent)
class LoyaltyEventAdmin(admin.ModelAdmin):
    list_display = ("user_email", "points_delta", "new_points_balance_after", "reason", "created_at")
    list_filter = ("reason", "created_at")
    search_fields = ("user__email", "description")
    readonly_fields = ("created_at",)

    def user_email(self, obj):
        return obj.user.email
    user_email.short_description = "Utilisateur"


@admin.register(PointValue)
class PointValueAdmin(admin.ModelAdmin):
    list_display = (
        "nombre_de_point",
        "valeur_un_point_frcfa",
        "duree_validite",
        "is_active",
        "updated_at",
    )
    list_editable = ("is_active", "duree_validite")
    list_filter = ("is_active",)


@admin.register(LoyaltyRewardRule)
class LoyaltyRewardRuleAdmin(admin.ModelAdmin):
    list_display = (
        "level",
        "montant_min",
        "montant_max",
        "nombre_point_gagner",
        "is_active",
    )
    list_editable = ("montant_min", "montant_max", "nombre_point_gagner", "is_active")
    ordering = ("montant_min",)
    list_filter = ("is_active",)
