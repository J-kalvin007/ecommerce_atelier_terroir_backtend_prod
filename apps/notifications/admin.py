from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from .models import NewsletterSubscriber, ContactMessage

@admin.register(NewsletterSubscriber)
class NewsletterSubscriberAdmin(admin.ModelAdmin):
    list_display = ("email", "status_badge", "created_at_formatted")
    list_filter = ("is_active", "created_at")
    search_fields = ("email",)
    readonly_fields = ("id", "created_at")
    ordering = ("-created_at",)
    
    fieldsets = (
        (_("Informations de l'abonné"), {
            "fields": ("id", "email", "is_active")
        }),
        (_("Métadonnées"), {
            "fields": ("created_at",),
            "classes": ("collapse",)
        }),
    )

    def status_badge(self, obj):
        if obj.is_active:
            return format_html(
                '<span style="background-color: #d1fae5; color: #065f46; padding: 4px 12px; border-radius: 9999px; font-size: 11px; font-weight: 600; letter-spacing: 0.5px; border: 1px solid #34d399; text-transform: uppercase;">Actif</span>'
            )
        return format_html(
            '<span style="background-color: #fee2e2; color: #991b1b; padding: 4px 12px; border-radius: 9999px; font-size: 11px; font-weight: 600; letter-spacing: 0.5px; border: 1px solid #f87171; text-transform: uppercase;">Inactif</span>'
        )
    status_badge.short_description = _("Statut")

    def created_at_formatted(self, obj):
        if obj.created_at:
            return obj.created_at.strftime("%d %b %Y, %H:%M")
        return "-"
    created_at_formatted.short_description = _("Date d'inscription")


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ("subject_truncate", "sender_info", "read_badge", "created_at_formatted")
    list_filter = ("is_read", "created_at")
    search_fields = ("name", "email", "subject", "message")
    readonly_fields = ("id", "created_at")
    ordering = ("is_read", "-created_at")
    
    fieldsets = (
        (_("Expéditeur"), {
            "fields": ("name", "email")
        }),
        (_("Contenu du message"), {
            "fields": ("subject", "message")
        }),
        (_("Statut & Traitement"), {
            "fields": ("is_read",),
            "description": "Marquez ce message comme lu une fois traité."
        }),
        (_("Métadonnées"), {
            "fields": ("id", "created_at"),
            "classes": ("collapse",)
        }),
    )

    def subject_truncate(self, obj):
        if len(obj.subject) > 45:
            return f"{obj.subject[:45]}..."
        return obj.subject
    subject_truncate.short_description = _("Sujet")

    def sender_info(self, obj):
        return format_html(
            '<div style="line-height: 1.4;">'
            '<strong style="color: #1f2937;">{}</strong><br>'
            '<a href="mailto:{}" style="color: #2563eb; font-size: 12px;">{}</a>'
            '</div>',
            obj.name, obj.email, obj.email
        )
    sender_info.short_description = _("Expéditeur")

    def read_badge(self, obj):
        if obj.is_read:
            return format_html(
                '<span style="background-color: #e0f2fe; color: #075985; padding: 4px 12px; border-radius: 9999px; font-size: 11px; font-weight: 600; letter-spacing: 0.5px; border: 1px solid #7dd3fc; text-transform: uppercase;">Lu</span>'
            )
        return format_html(
            '<span style="background-color: #fef3c7; color: #92400e; padding: 4px 12px; border-radius: 9999px; font-size: 11px; font-weight: 600; letter-spacing: 0.5px; border: 1px solid #fcd34d; text-transform: uppercase;">Non Lu</span>'
        )
    read_badge.short_description = _("Statut")

    def created_at_formatted(self, obj):
        if obj.created_at:
            return obj.created_at.strftime("%d %b %Y, %H:%M")
        return "-"
    created_at_formatted.short_description = _("Reçu le")
