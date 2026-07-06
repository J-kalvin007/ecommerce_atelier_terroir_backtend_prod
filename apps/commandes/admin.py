from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.db.models import Sum, Count

from apps.commandes.models import (
    Cart,
    CartItem,
    Order,
    OrderItem,
    OrderStatusHistory,
)


class OrderItemInline(admin.TabularInline):
    """
    Affiche la liste des produits achetés directement dans la fiche commande.
    En lecture seule pour éviter de modifier une vente déjà conclue.
    """
    model = OrderItem
    extra = 0
    can_delete = False
    readonly_fields = (
        "product",
        "product_name",
        "product_sku",
        "quantity",
        "unit_price",
        "subtotal",
    )
    autocomplete_fields = ("product",)

    def has_add_permission(self, request, obj=None):
        return False


class OrderStatusHistoryInline(admin.TabularInline):
    """
    Affiche l'historique complet des changements de statut.
    """
    model = OrderStatusHistory
    extra = 0
    can_delete = False
    readonly_fields = (
        "old_status",
        "new_status",
        "comment",
        "changed_by",
        "created_at",
    )
    autocomplete_fields = ("changed_by",)

    def has_add_permission(self, request, obj=None):
        return False


class CartItemInline(admin.TabularInline):
    """
    Affiche les articles du panier directement dans la fiche panier.
    """
    model = CartItem
    extra = 0
    can_delete = True
    readonly_fields = ("id", "product", "quantity", "unit_price_display", "subtotal_display", "created_at")
    fields = ("product", "quantity", "unit_price_display", "subtotal_display", "created_at")

    def unit_price_display(self, obj):
        if obj.product:
            return format_html('<span style="font-weight:bold;color:#1f4d3f;">{} FCFA</span>', obj.product.price)
        return "—"
    unit_price_display.short_description = "Prix unitaire"

    def subtotal_display(self, obj):
        if obj.product:
            try:
                total = float(obj.product.price) * obj.quantity
                return format_html('<span style="font-weight:bold;color:#8b5e34;">{:.0f} FCFA</span>', total)
            except (ValueError, TypeError):
                pass
        return "—"
    subtotal_display.short_description = "Sous-total"

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ("id", "user_email", "items_count_display", "total_display", "created_at", "updated_at")
    search_fields = ("user__email", "user__name")
    autocomplete_fields = ("user",)
    readonly_fields = ("id", "created_at", "updated_at", "items_count_display", "total_display")
    inlines = [CartItemInline]
    list_per_page = 30

    fieldsets = (
        ("🛒 Panier", {
            "fields": ("id", "user")
        }),
        ("📊 Résumé", {
            "fields": ("items_count_display", "total_display"),
        }),
        ("🕒 Dates", {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",)
        }),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("user").prefetch_related("items__product")

    def user_email(self, obj):
        if obj.user:
            return format_html('<span style="font-weight:bold;">{}</span>', obj.user.email)
        return "—"
    user_email.short_description = "Client"
    user_email.admin_order_field = "user__email"

    def items_count_display(self, obj):
        count = obj.items.count()
        color = "#1f4d3f" if count > 0 else "#aaa"
        return format_html('<b style="color:{};">{}</b> article(s)', color, count)
    items_count_display.short_description = "Articles"

    def total_display(self, obj):
        try:
            total = sum(
                float(item.product.price) * item.quantity
                for item in obj.items.select_related("product").all()
                if item.product
            )
            return format_html('<span style="font-weight:bold;color:#1f4d3f;">{:.0f} FCFA</span>', total)
        except Exception:
            return "—"
    total_display.short_description = "Total panier"


@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    list_display = ("id", "cart_user", "product_display", "quantity", "unit_price_display", "subtotal_display", "created_at")
    search_fields = ("product__name", "product__sku", "cart__user__email")
    autocomplete_fields = ("cart", "product")
    list_filter = ("created_at",)
    readonly_fields = ("id", "unit_price_display", "subtotal_display", "created_at", "updated_at")
    list_per_page = 40

    fieldsets = (
        ("🛍️ Élément", {
            "fields": ("id", "cart", "product", "quantity")
        }),
        ("💰 Prix", {
            "fields": ("unit_price_display", "subtotal_display")
        }),
        ("🕒 Dates", {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",)
        }),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("cart__user", "product")

    def cart_user(self, obj):
        if obj.cart and obj.cart.user:
            return format_html('<span style="font-weight:bold;">{}</span>', obj.cart.user.email)
        return "—"
    cart_user.short_description = "Client"
    cart_user.admin_order_field = "cart__user__email"

    def product_display(self, obj):
        if obj.product:
            return format_html('<span style="font-weight:bold;color:#1f4d3f;">{}</span>', obj.product.name)
        return "—"
    product_display.short_description = "Produit"

    def unit_price_display(self, obj):
        if obj.product:
            return format_html('<span style="font-weight:bold;">{} FCFA</span>', obj.product.price)
        return "—"
    unit_price_display.short_description = "Prix unitaire"

    def subtotal_display(self, obj):
        if obj.product:
            try:
                total = float(obj.product.price) * obj.quantity
                return format_html('<span style="font-weight:bold;color:#8b5e34;">{:.0f} FCFA</span>', total)
            except (ValueError, TypeError):
                pass
        return "—"
    subtotal_display.short_description = "Sous-total"




@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        'order_number_display', 'client_link', 'status_badge',
        'items_count', 'amount_display',
        'location_display', 'created_at',
    )
    list_display_links = ('order_number_display',)
    list_filter = ('status', 'country', 'city', 'created_at')
    search_fields = ('reference', 'user__email', 'phone_livraison')
    autocomplete_fields = ('user',)
    readonly_fields = (
        'id', 'reference', 'created_at', 'updated_at', 
        'order_summary_html', 'shipping_address_html', 
        'items_total', 'discount_amount', 'tax_amount', 
        'frais_livraison', 'total_final'
    )
    inlines = [OrderItemInline, OrderStatusHistoryInline]
    list_per_page = 25
    date_hierarchy = 'created_at'
    
    actions = ['mark_preparing', 'mark_shipped', 'mark_delivered', 'cancel_orders']

    fieldsets = (
        ('📋 Commande', {
            'fields': ('reference', 'user', 'status', 'order_summary_html')
        }),
        ('💰 Montants', {
            'fields': ('items_total', 'frais_livraison', 'discount_amount', 'tax_amount', 'total_final')
        }),
        ('🚚 Livraison', {
            'fields': ('shipping_address_html', 'address_livraison', 'city', 'country', 'phone_livraison')
        }),
        ('💳 Paiement', {
            'fields': ('paid_at',),
            'classes': ('collapse',)
        }),
        ('📝 Notes', {
            'fields': ('notes',)
        }),
        ('🕒 Historique', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user').prefetch_related('items')

    def order_number_display(self, obj):
        return format_html('<span style="color:#6C63FF;font-weight:bold;font-family:monospace;">{}</span>', obj.reference)
    order_number_display.short_description = "Référence"
    order_number_display.admin_order_field = 'reference'

    def client_link(self, obj):
        if obj.user:
            return format_html('<span style="font-weight:bold;">{}</span>', obj.user.email)
        return "—"
    client_link.short_description = "Client"
    client_link.admin_order_field = 'user__email'

    def status_badge(self, obj):
        colors = {
            'draft': '#9e9e9e', 'pending_payment': '#ffb300', 'paid': '#1e88e5',
            'confirmed': '#1976d2', 'processing': '#f57c00', 'shipped': '#7b1fa2',
            'delivered': '#388e3c', 'cancelled': '#d32f2f', 'refunded': '#455a64',
        }
        icons = {
            'draft': '📝', 'pending_payment': '⏳', 'paid': '💲',
            'confirmed': '✔', 'processing': '📦', 'shipped': '🚚',
            'delivered': '✅', 'cancelled': '❌', 'refunded': '↩️',
        }
        color = colors.get(obj.status, '#999')
        icon = icons.get(obj.status, '')
        return format_html(
            '<span style="background:{};color:white;padding:4px 10px;border-radius:6px;font-weight:bold;font-size:11px;">{} {}</span>',
            color, icon, obj.get_status_display()
        )
    status_badge.short_description = "Statut"
    status_badge.admin_order_field = 'status'

    def items_count(self, obj):
        return format_html('<b>{}</b> article(s)', obj.items.count())
    items_count.short_description = "Articles"

    def amount_display(self, obj):
        html = format_html('<span style="font-weight:bold;color:#1a237e;">{} FCFA</span>', obj.total_final)
        if obj.discount_amount and obj.discount_amount > 0:
            html = format_html('{}<br><span style="color:#d32f2f;font-size:10px;">-{} promo</span>', html, obj.discount_amount)
        return html
    amount_display.short_description = "Total"
    amount_display.admin_order_field = 'total_final'

    def location_display(self, obj):
        return format_html('<b>{}</b>, {}', obj.city, obj.country)
    location_display.short_description = "Lieu"

    def order_summary_html(self, obj):
        items = obj.items.all()
        if not items.exists():
            return format_html('<span style="color:#aaa;">Aucun article</span>')
        rows = []
        for item in items:
            rows.append(format_html(
                '<tr><td style="padding:5px 10px;">{}</td><td style="padding:5px 10px;"><code>{}</code></td>'
                '<td style="padding:5px 10px;text-align:center;">{}</td>'
                '<td style="padding:5px 10px;text-align:right;">{} FCFA</td>'
                '<td style="padding:5px 10px;text-align:right;font-weight:bold;">{} FCFA</td></tr>',
                item.product_name, item.product_sku, item.quantity, item.unit_price, item.subtotal,
            ))
        return format_html(
            '<table style="border-collapse:collapse;width:100%;">'
            '<thead><tr style="background:rgba(108,99,255,0.1);border-bottom:2px solid rgba(108,99,255,0.2);">'
            '<th style="padding:6px 10px;text-align:left;">Produit</th><th style="padding:6px 10px;text-align:left;">SKU</th>'
            '<th style="padding:6px 10px;text-align:center;">Qté</th><th style="padding:6px 10px;text-align:right;">P.U</th><th style="padding:6px 10px;text-align:right;">Total</th>'
            '</tr></thead><tbody>{}</tbody></table>',
            format_html(''.join(str(r) for r in rows))
        )
    order_summary_html.short_description = "Détail articles"

    def shipping_address_html(self, obj):
        if not obj.address_livraison:
            return format_html('<span style="color:#aaa;">Non renseignée</span>')
        return format_html(
            '<div style="padding:8px;background:#f9f9f9;border-radius:8px;line-height:1.8;">'
            '📍 {}<br>🏙️ {}<br>🌍 {}<br>📞 {}</div>',
            obj.address_livraison, obj.city, obj.country, obj.phone_livraison,
        )
    shipping_address_html.short_description = "Adresse livraison"

    def mark_preparing(self, request, queryset):
        updated = queryset.filter(status__in=['paid', 'confirmed']).update(status='processing')
        self.message_user(request, f"📦 {updated} commande(s) en préparation")
    mark_preparing.short_description = "📦 Passer en préparation"

    def mark_shipped(self, request, queryset):
        updated = queryset.filter(status='processing').update(status='shipped')
        self.message_user(request, f"🚚 {updated} commande(s) expédiée(s)")
    mark_shipped.short_description = "🚚 Marquer expédié"

    def mark_delivered(self, request, queryset):
        updated = queryset.filter(status='shipped').update(status='delivered')
        self.message_user(request, f"✅ {updated} commande(s) livrée(s)")
    mark_delivered.short_description = "✅ Marquer livré"

    def cancel_orders(self, request, queryset):
        updated = queryset.filter(status__in=['draft', 'pending_payment', 'paid', 'confirmed']).update(status='cancelled')
        self.message_user(request, f"❌ {updated} commande(s) annulée(s)")
    cancel_orders.short_description = "❌ Annuler"

    def changelist_view(self, request, extra_context=None):
        response = super().changelist_view(request, extra_context)
        try:
            qs = response.context_data['cl'].queryset
            response.context_data['stats'] = qs.aggregate(
                total_revenue=Sum('total_final'), total_orders=Count('id'),
            )
        except Exception:
            pass
        return response


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = (
        "order",
        "product_name",
        "product_sku",
        "quantity",
        "unit_price",
        "subtotal",
    )
    search_fields = ("product_name", "product_sku", "order__reference")
    autocomplete_fields = ("order", "product")
    readonly_fields = ("id", "created_at", "updated_at")

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("order")


@admin.register(OrderStatusHistory)
class OrderStatusHistoryAdmin(admin.ModelAdmin):
    list_display = (
        "order",
        "old_status",
        "new_status",
        "changed_by",
        "created_at",
    )
    search_fields = ("order__reference",)
    list_filter = ("new_status", "created_at")
    autocomplete_fields = ("order", "changed_by")
    readonly_fields = ("id", "created_at", "updated_at")
    ordering = ("-created_at",)

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("order", "changed_by")