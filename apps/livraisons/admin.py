from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from .models import FraisLivraison, Delivery, DeliveryStatus

@admin.register(FraisLivraison)
class FraisLivraisonAdmin(admin.ModelAdmin):
    list_display = ("prix_badge", "coordonnee_admin", "status_badge", "created_at_formatted")
    list_filter = ("is_active", "created_at")
    search_fields = ("prix_livraison", "coordonnee_admin")
    readonly_fields = ("id", "created_at", "updated_at")
    ordering = ("-created_at",)
    
    fieldsets = (
        (_("Tarification"), {
            "fields": ("prix_livraison",)
        }),
        (_("Localisation & Statut"), {
            "fields": ("coordonnee_admin", "is_active")
        }),
        (_("Métadonnées"), {
            "fields": ("id", "created_at", "updated_at"),
            "classes": ("collapse",)
        }),
    )

    def prix_badge(self, obj):
        return format_html(
            '<span style="font-weight: bold; color: #111827; font-size: 14px;">{} FCFA / Km</span>',
            obj.prix_livraison
        )
    prix_badge.short_description = _("Prix de livraison")

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
    created_at_formatted.short_description = _("Dernière mise à jour")


@admin.register(Delivery)
class DeliveryAdmin(admin.ModelAdmin):
    list_display = ("order_info", "status_badge", "delivery_person_info", "tracking_info", "dates_info")
    list_filter = ("status", "created_at", "delivery_person")
    search_fields = ("order__reference", "tracking_number", "delivery_address")
    raw_id_fields = ("order", "delivery_person")
    date_hierarchy = "created_at"
    readonly_fields = ("id", "created_at", "updated_at")
    list_select_related = ("order", "delivery_person")

    fieldsets = (
        (_("Informations Commande"), {
            "fields": ("order", "status")
        }),
        (_("Logistique & Affectation"), {
            "fields": ("delivery_person", "tracking_number", "delivery_address")
        }),
        (_("Plannification & Suivi"), {
            "fields": ("estimated_delivery_date", "actual_delivery_date", "notes")
        }),
        (_("Métadonnées"), {
            "fields": ("id", "created_at", "updated_at"),
            "classes": ("collapse",)
        }),
    )

    def order_info(self, obj):
        return format_html(
            '<div style="line-height: 1.4;">'
            '<strong style="color: #4f46e5; font-size: 13px;">{}</strong><br>'
            '<span style="color: #6b7280; font-size: 11px;">ID: {}</span>'
            '</div>',
            obj.order.reference, str(obj.id)[:8]
        )
    order_info.short_description = _("Commande")

    def status_badge(self, obj):
        colors = {
            DeliveryStatus.PENDING: {"bg": "#fef3c7", "text": "#92400e", "border": "#fcd34d"},
            DeliveryStatus.IN_TRANSIT: {"bg": "#dbeafe", "text": "#1e40af", "border": "#93c5fd"},
            DeliveryStatus.DELIVERED: {"bg": "#dcfce3", "text": "#166534", "border": "#86efac"},
            DeliveryStatus.CANCELLED: {"bg": "#fee2e2", "text": "#991b1b", "border": "#f87171"},
        }
        color = colors.get(obj.status, {"bg": "#f3f4f6", "text": "#374151", "border": "#d1d5db"})
        return format_html(
            '<span style="background-color: {}; color: {}; padding: 4px 12px; border-radius: 9999px; font-size: 11px; font-weight: 600; letter-spacing: 0.5px; border: 1px solid {}; text-transform: uppercase;">{}</span>',
            color["bg"], color["text"], color["border"], obj.get_status_display()
        )
    status_badge.short_description = _("Statut")

    def delivery_person_info(self, obj):
        if obj.delivery_person:
            return format_html(
                '<div style="display: flex; align-items: center; gap: 8px;">'
                '<div style="width: 24px; height: 24px; border-radius: 50%; background-color: #e5e7eb; display: flex; align-items: center; justify-content: center; font-weight: bold; color: #4b5563; font-size: 10px;">{}</div>'
                '<span style="font-weight: 500; color: #111827;">{}</span>'
                '</div>',
                obj.delivery_person.email[0].upper(), obj.delivery_person.email
            )
        return format_html('<span style="color: #9ca3af; font-style: italic;">Non assigné</span>')
    delivery_person_info.short_description = _("Livreur")

    def tracking_info(self, obj):
        if obj.tracking_number:
            return format_html(
                '<span style="background-color: #f3f4f6; color: #4b5563; padding: 3px 8px; border-radius: 6px; font-family: monospace; font-size: 12px; border: 1px solid #e5e7eb;">{}</span>',
                obj.tracking_number
            )
        return "-"
    tracking_info.short_description = _("Suivi")

    def dates_info(self, obj):
        est = obj.estimated_delivery_date.strftime("%d/%m/%y") if obj.estimated_delivery_date else "-"
        act = obj.actual_delivery_date.strftime("%d/%m/%y") if obj.actual_delivery_date else "-"
        
        return format_html(
            '<div style="font-size: 11px; color: #6b7280; line-height: 1.5;">'
            '<strong>Est:</strong> {}<br>'
            '<strong>Rée:</strong> <span style="color: {};">{}</span>'
            '</div>',
            est,
            "#16a34a" if obj.actual_delivery_date else "#6b7280",
            act
        )
    dates_info.short_description = _("Délais")


# ─────────────────────────────────────────────────────────────────────────────
# LIVREUR ADMIN
# ─────────────────────────────────────────────────────────────────────────────

from .models import Livreur

@admin.register(Livreur)
class LivreurAdmin(admin.ModelAdmin):
    list_display = (
        "nom_complet_badge", 
        "telephone_info", 
        "vehicule_badge", 
        "zone_livraison_info",
        "status_badge"
    )
    list_filter = ("is_active", "type_vehicule", "created_at")
    search_fields = ("nom", "prenom", "telephone", "email", "zone_livraison")
    readonly_fields = ("id", "created_at", "updated_at")
    list_select_related = ("user",)
    
    actions = ['desactiver_livreurs']

    fieldsets = (
        (_("Identité & Contact"), {
            "fields": (("prenom", "nom"), "telephone", "email")
        }),
        (_("Opérationnel"), {
            "fields": ("type_vehicule", "zone_livraison", "user")
        }),
        (_("Administration"), {
            "fields": ("is_active", "notes")
        }),
        (_("Métadonnées"), {
            "fields": ("id", "created_at", "updated_at"),
            "classes": ("collapse",)
        }),
    )

    def nom_complet_badge(self, obj):
        return format_html(
            '<strong style="color: #111827; font-size: 13px;">{}</strong>',
            obj.nom_complet
        )
    nom_complet_badge.short_description = _("Livreur")
    nom_complet_badge.admin_order_field = 'nom'

    def telephone_info(self, obj):
        return format_html(
            '<span style="font-family: monospace; font-size: 12px; color: #4b5563;">{}</span>',
            obj.telephone
        )
    telephone_info.short_description = _("Téléphone")

    def vehicule_badge(self, obj):
        return format_html(
            '<span style="background-color: #f3f4f6; color: #374151; padding: 3px 8px; border-radius: 6px; font-size: 11px; border: 1px solid #d1d5db; text-transform: uppercase;">{}</span>',
            obj.get_type_vehicule_display()
        )
    vehicule_badge.short_description = _("Véhicule")
    vehicule_badge.admin_order_field = 'type_vehicule'

    def zone_livraison_info(self, obj):
        return obj.zone_livraison or "-"
    zone_livraison_info.short_description = _("Zone")

    def status_badge(self, obj):
        if obj.is_active:
            return format_html(
                '<span style="background-color: #d1fae5; color: #065f46; padding: 4px 12px; border-radius: 9999px; font-size: 11px; font-weight: 600; letter-spacing: 0.5px; border: 1px solid #34d399; text-transform: uppercase;">Actif</span>'
            )
        return format_html(
            '<span style="background-color: #fee2e2; color: #991b1b; padding: 4px 12px; border-radius: 9999px; font-size: 11px; font-weight: 600; letter-spacing: 0.5px; border: 1px solid #f87171; text-transform: uppercase;">Inactif</span>'
        )
    status_badge.short_description = _("Statut")
    status_badge.admin_order_field = 'is_active'

    @admin.action(description=_("Désactiver logiquement les livreurs sélectionnés"))
    def desactiver_livreurs(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(
            request, 
            _("%(count)d livreurs ont été désactivés logiquement.") % {"count": updated}
        )
