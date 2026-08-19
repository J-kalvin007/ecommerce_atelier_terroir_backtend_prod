from django.contrib import admin
from django.utils.html import format_html

from .models import Recette


@admin.register(Recette)
class RecetteAdmin(admin.ModelAdmin):

    list_display = (
        "image_preview",
        "nom",
        "slug",
        "product",
        "pack",
        "is_active",
        "created_at",
    )

    list_filter = (
        "is_active",
        "created_at",
    )

    search_fields = (
        "nom",
        "slug",
        "description",
        "ingredients",
        "product__name",
        "pack__name",
    )

    autocomplete_fields = (
        "product",
        "pack",
    )

    prepopulated_fields = {
        "slug": ("nom",)
    }

    readonly_fields = (
        "created_at",
        "updated_at",
        "video_preview",
    )

    fieldsets = (
        (
            "Informations générales",
            {
                "fields": (
                    "nom",
                    "slug",
                    "description",
                    "is_active",
                )
            },
        ),
        (
            "Contenu de la recette",
            {
                "fields": (
                    "ingredients",
                    "instructions",
                )
            },
        ),
        (
            "Média",
            {
                "fields": (
                    "video_url",
                    "video",
                    "video_preview",
                    "image_1",
                    "image_2",
                )
            },
        ),
        (
            "Association produit / pack",
            {
                "description": (
                    "Une recette est liée à un produit OU à un pack, jamais aux deux à la fois."
                ),
                "fields": (
                    "product",
                    "pack",
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

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("product", "pack")

    def image_preview(self, obj):

        if obj.image_1:
            return format_html(
                '<img src="{}" '
                'width="60" '
                'height="60" '
                'style="border-radius:8px;'
                'object-fit:cover;" />',
                obj.image_1.url,
            )

        return "—"

    image_preview.short_description = "Image"

    def video_preview(self, obj):

        if obj.video:
            return format_html(
                '<video src="{}" controls style="max-height:240px;border-radius:8px;"></video>',
                obj.video.url,
            )

        return "Aucune vidéo"

    video_preview.short_description = "Aperçu vidéo"
