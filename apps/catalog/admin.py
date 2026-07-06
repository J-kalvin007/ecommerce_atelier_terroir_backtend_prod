from django.contrib import admin
from django.utils.html import format_html
from .models import Favorite
from .models import Rating


from .models import (
    Category,
    Product,
    ProductImage,
    ProductVariant,
)


# =====================================================
# PRODUCT IMAGE INLINE
# =====================================================

class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1

    fields = (
        "image",
        "alt_text",
        "is_primary",
    )


# =====================================================
# PRODUCT VARIANT INLINE
# =====================================================

class ProductVariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 1

    fields = (
        "name",
        "sku",
        "price",
        "stock",
        "weight_grams",
    )


# =====================================================
# CATEGORY
# =====================================================

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):

    list_display = (
        "name",
        "parent",
        "slug",
        "created_at",
    )

    search_fields = (
        "name",
        "slug",
    )

    prepopulated_fields = {
        "slug": ("name",)
    }

    list_filter = (
        "created_at",
    )

    ordering = (
        "name",
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("parent")


# =====================================================
# PRODUCT
# =====================================================

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):

    list_display = (
        "image_preview",
        "name",
        "sku",
        "category",
        "price",
        "stock",
        "product_type",
        "is_top",
        "created_at",
    )

    list_editable = (
        "price",
        "stock",
        "is_top",
    )

    search_fields = (
        "name",
        "sku",
        "slug",
        "description",
    )

    list_filter = (
        "category",
        "product_type",
        "is_top",
        "created_at",
    )

    prepopulated_fields = {
        "slug": ("name",)
    }

    readonly_fields = (
        "created_at",
        "updated_at",
        "image_preview_large",
    )

    inlines = [
        ProductImageInline,
        ProductVariantInline,
    ]

    fieldsets = (
        (
            "Informations générales",
            {
                "fields": (
                    "name",
                    "sku",
                    "slug",
                    "category",
                    "product_type",
                    "description",
                )
            },
        ),
        (
            "Tarification",
            {
                "fields": (
                    "price",
                    "stock",
                    "weight_grams",
                )
            },
        ),
        (
            "SEO",
            {
                "classes": (
                    "collapse",
                ),
                "fields": (
                    "seo_title",
                    "seo_description",
                ),
            },
        ),
        (
            "Relations",
            {
                "fields": (
                    "related_products",
                    "is_top",
                )
            },
        ),
        (
            "Média",
            {
                "fields": (
                    "image_preview_large",
                )
            },
        ),
        (
            "Historique",
            {
                "fields": (
                    "created_at",
                    "updated_at",
                )
            },
        ),
    )

    filter_horizontal = (
        "related_products",
    )

    def get_queryset(self, request):
        from django.db.models import Prefetch
        return super().get_queryset(request).select_related(
            "category"
        ).prefetch_related(
            Prefetch(
                "images",
                queryset=ProductImage.objects.filter(is_primary=True),
                to_attr="primary_images"
            )
        )

    def image_preview(self, obj):

        if hasattr(obj, "primary_images") and obj.primary_images:
            image = obj.primary_images[0]

            if image.image:
                return format_html(
                    '<img src="{}" '
                    'width="60" '
                    'height="60" '
                    'style="border-radius:8px;'
                    'object-fit:cover;" />',
                    image.image.url,
                )

        return "—"

    image_preview.short_description = "Image"

    def image_preview_large(self, obj):

        if hasattr(obj, "primary_images") and obj.primary_images:
            image = obj.primary_images[0]

            if image.image:
                return format_html(
                    '<img src="{}" '
                    'style="max-height:300px;'
                    'border-radius:12px;" />',
                    image.image.url,
                )

        return "Aucune image"

    image_preview_large.short_description = (
        "Aperçu principal"
    )


# =====================================================
# PRODUCT IMAGE
# =====================================================

@admin.register(ProductImage)
class ProductImageAdmin(admin.ModelAdmin):

    list_display = (
        "preview",
        "product",
        "is_primary",
        "created_at",
    )

    list_filter = (
        "is_primary",
    )

    search_fields = (
        "product__name",
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("product")

    def preview(self, obj):

        if obj.image:

            return format_html(
                '<img src="{}" '
                'width="60" '
                'height="60" '
                'style="border-radius:8px;" />',
                obj.image.url,
            )

        return "—"

    preview.short_description = "Image"


# =====================================================
# PRODUCT VARIANT
# =====================================================

@admin.register(ProductVariant)
class ProductVariantAdmin(admin.ModelAdmin):

    list_display = (
        "product",
        "name",
        "sku",
        "price",
        "stock",
    )

    search_fields = (
        "name",
        "sku",
        "product__name",
    )

    list_filter = (
        "product",
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("product")











@admin.register(Favorite)
class FavoriteAdmin(admin.ModelAdmin):
    list_display = ("user_email", "product_name", "created_at")
    list_filter = ("created_at",)
    search_fields = ("user__email", "product__name")
    autocomplete_fields = ("user", "product")
    date_hierarchy = "created_at"

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("user", "product")

    def user_email(self, obj):
        return obj.user.email
    user_email.short_description = "Utilisateur"

    def product_name(self, obj):
        return obj.product.name
    product_name.short_description = "Produit"













@admin.register(Rating)
class RatingAdmin(admin.ModelAdmin):
    list_display = ("user_email", "product_name", "score_badge", "updated_at")
    list_filter = ("score", "updated_at")
    search_fields = ("user__email", "product__name")
    autocomplete_fields = ("user", "product")
    readonly_fields = ("created_at", "updated_at")

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("user", "product")

    def user_email(self, obj):
        return obj.user.email
    user_email.short_description = "Utilisateur"

    def product_name(self, obj):
        return obj.product.name
    product_name.short_description = "Produit"

    def score_badge(self, obj):
        """Affiche le score sous forme d'étoiles visuelles."""
        stars = "★" * obj.score + "☆" * (5 - obj.score)
        color = "#fbc02d" if obj.score >= 3 else "#d32f2f"
        return format_html(
            '<span style="color:{}; font-size:16px; font-weight:bold;">{}</span>',
            color, stars
        )
    score_badge.short_description = "Note"