from django.contrib import admin
from django.db.models import F
from django.utils import timezone

from .models import PromoCode, Soldes, Banner


@admin.register(PromoCode)
class PromoCodeAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "type",
        "value",
        "number_times_used",
        "is_active",
        "starts_at",
        "expires_at"
    )
    list_filter = ("type", "is_active", "starts_at", "expires_at")
    search_fields = ("code", "description")
    readonly_fields = ("number_times_used", "created_at", "updated_at")
    filter_horizontal = ("applicable_products", "applicable_categories", "restricted_to_tiers")
    actions = ["deactivate_selected", "duplicate_selected"]

    def deactivate_selected(self, request, queryset):
        """Désactive les codes promo sélectionnés."""
        count = queryset.update(is_active=False)
        self.message_user(request, f"{count} code(s) promo désactivé(s).")
    deactivate_selected.short_description = "Désactiver les codes sélectionnés"

    def duplicate_selected(self, request, queryset):
        """Duplique les codes promo sélectionnés."""
        import uuid
        for original in queryset:
            original.pk = None
            original.code = f"{original.code}-COPY-{uuid.uuid4().hex[:4].upper()}"
            original.number_times_used = 0
            original.save()
        self.message_user(request, f"{queryset.count()} code(s) promo dupliqué(s).")
    duplicate_selected.short_description = "Dupliquer les codes sélectionnés"



@admin.register(Soldes)
class FlashSaleAdmin(admin.ModelAdmin):
    list_display = (
        "product",
        "variant",
        "sale_price",
        "original_price",
        "discount_percent",
        "product_sold_count",
        "quota_stock_limit",
        "is_running"
    )
    list_filter = ("is_active", "starts_at", "ends_at")
    search_fields = ("product__name", "variant__name")
    readonly_fields = ("original_price", "product_sold_count", "created_at", "updated_at")
    autocomplete_fields = ("product", "variant")


@admin.register(Banner)
class BannerAdmin(admin.ModelAdmin):
    list_display = ("title", "banner_type", "position", "is_active", "starts_at", "ends_at")
    list_filter = ("banner_type", "is_active")
    search_fields = ("title", "subtitle")
    list_editable = ("position", "is_active")
