from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from django.contrib import messages
from .models import NewsletterSubscriber, ContactMessage, CustomerReview

@admin.register(NewsletterSubscriber)
class NewsletterSubscriberAdmin(admin.ModelAdmin):
    list_display = ("email", "status_badge", "created_at_formatted")
    list_filter = ("is_active", "created_at")
    search_fields = ("email",)
    readonly_fields = ("id", "created_at")
    ordering = ("-created_at",)
    actions = ["activate_subscribers", "deactivate_subscribers"]
    
    fieldsets = (
        (_("Informations de l'abonné"), {
            "fields": ("id", "email", "is_active")
        }),
        (_("Métadonnées"), {
            "fields": ("created_at",),
            "classes": ("collapse",)
        }),
    )

    @admin.action(description=_("Activer les abonnés sélectionnés"))
    def activate_subscribers(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f"{updated} abonné(s) activé(s) avec succès.", messages.SUCCESS)

    @admin.action(description=_("Désactiver les abonnés sélectionnés"))
    def deactivate_subscribers(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f"{updated} abonné(s) désactivé(s) avec succès.", messages.SUCCESS)

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
    actions = ["mark_as_read", "mark_as_unread"]
    
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

    @admin.action(description=_("Marquer comme lu"))
    def mark_as_read(self, request, queryset):
        updated = queryset.update(is_read=True)
        self.message_user(request, f"{updated} message(s) marqué(s) comme lu(s).", messages.SUCCESS)

    @admin.action(description=_("Marquer comme non lu"))
    def mark_as_unread(self, request, queryset):
        updated = queryset.update(is_read=False)
        self.message_user(request, f"{updated} message(s) marqué(s) comme non lu(s).", messages.SUCCESS)

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


@admin.register(CustomerReview)
class CustomerReviewAdmin(admin.ModelAdmin):
    list_display = ("reviewer_info", "city", "rating_badge", "status_badge", "created_at_formatted")
    list_filter = ("is_approved", "rating", "created_at")
    search_fields = ("first_name", "last_name", "city", "message")
    readonly_fields = ("id", "created_at")
    ordering = ("is_approved", "-created_at")
    actions = ["approve_reviews", "unapprove_reviews"]

    fieldsets = (
        (_("Auteur"), {
            "fields": ("first_name", "last_name", "city", "profile_image")
        }),
        (_("Avis"), {
            "fields": ("rating", "message")
        }),
        (_("Statut & Traitement"), {
            "fields": ("is_approved",),
            "description": "Approuver cet avis pour l'afficher sur le site."
        }),
        (_("Métadonnées"), {
            "fields": ("id", "created_at"),
            "classes": ("collapse",)
        }),
    )

    @admin.action(description=_("Approuver les avis sélectionnés"))
    def approve_reviews(self, request, queryset):
        updated = queryset.update(is_approved=True)
        self.message_user(request, f"{updated} avis approuvé(s) avec succès.", messages.SUCCESS)

    @admin.action(description=_("Désapprouver les avis sélectionnés"))
    def unapprove_reviews(self, request, queryset):
        updated = queryset.update(is_approved=False)
        self.message_user(request, f"{updated} avis désapprouvé(s) avec succès.", messages.SUCCESS)

    def reviewer_info(self, obj):
        return format_html(
            '<strong>{} {}</strong>',
            obj.first_name, obj.last_name
        )
    reviewer_info.short_description = _("Auteur")

    def rating_badge(self, obj):
        stars = "⭐" * obj.rating
        empty_stars = "☆" * (5 - obj.rating)
        return format_html(
            '<span style="color: #fbbf24; font-size: 14px; letter-spacing: 2px;">{}{}</span>',
            stars, empty_stars
        )
    rating_badge.short_description = _("Note")

    def status_badge(self, obj):
        if obj.is_approved:
            return format_html(
                '<span style="background-color: #d1fae5; color: #065f46; padding: 4px 12px; border-radius: 9999px; font-size: 11px; font-weight: 600; letter-spacing: 0.5px; border: 1px solid #34d399; text-transform: uppercase;">Approuvé</span>'
            )
        return format_html(
            '<span style="background-color: #fee2e2; color: #991b1b; padding: 4px 12px; border-radius: 9999px; font-size: 11px; font-weight: 600; letter-spacing: 0.5px; border: 1px solid #f87171; text-transform: uppercase;">En attente</span>'
        )
    status_badge.short_description = _("Statut")

    def created_at_formatted(self, obj):
        if obj.created_at:
            return obj.created_at.strftime("%d %b %Y, %H:%M")
        return "-"
    created_at_formatted.short_description = _("Soumis le")
