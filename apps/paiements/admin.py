from django.contrib import admin
from django.db import transaction
from django.utils.html import format_html

from .models import Payment, Wallet, WalletTransaction, GlobalTransaction
from .services import PaymentService


@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = ("user_email", "balance","reference", "status_badge", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("user__email",)
    autocomplete_fields = ("user",)
    readonly_fields = ("created_at", "updated_at")

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("user")

    def user_email(self, obj):
        return format_html('<b>{}</b>', obj.user.email)
    user_email.short_description = "Utilisateur"

    def status_badge(self, obj):
        color = "#388e3c" if obj.status == "active" else "#d32f2f"
        return format_html(
            '<span style="background:{};color:white;padding:4px 10px;border-radius:6px;font-weight:bold;font-size:11px;">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = "Statut"


@admin.register(WalletTransaction)
class WalletTransactionAdmin(admin.ModelAdmin):
    list_display = ("reference", "wallet_user", "transaction_type", "amount", "status_badge", "created_at")
    list_filter = ("transaction_type", "status", "created_at")
    search_fields = ("reference", "wallet__user__email")
    autocomplete_fields = ("wallet", "order")
    readonly_fields = ("wallet", "order", "metadata", "created_at", "updated_at")

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("wallet__user", "order")

    def wallet_user(self, obj):
        return obj.wallet.user.email
    wallet_user.short_description = "Propriétaire"

    def status_badge(self, obj):
        colors = {'pending': '#f57c00', 'completed': '#388e3c', 'failed': '#d32f2f'}
        color = colors.get(obj.status, '#999')
        return format_html(
            '<span style="background:{};color:white;padding:4px 10px;border-radius:6px;font-weight:bold;font-size:11px;">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = "Statut"


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("id", "provider", "payment_type", "amount", "status_badge", "order_ref", "created_at")
    list_filter = ("provider", "payment_type", "status", "created_at")
    search_fields = ("reference_externe", "order__reference")
    autocomplete_fields = ("order",)
    readonly_fields = ( "metadata", "created_at", "updated_at")

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("order")

    def order_ref(self, obj):
        if obj.order:
            return format_html('<span style="color:#6C63FF;font-weight:bold;">{}</span>', obj.order.reference)
        return "-"
    order_ref.short_description = "Commande"

    def status_badge(self, obj):
        colors = {'pending': '#f57c00', 'successful': '#388e3c', 'failed': '#d32f2f', 'refunded': '#455a64'}
        color = colors.get(obj.status, '#999')
        return format_html(
            '<span style="background:{};color:white;padding:4px 10px;border-radius:6px;font-weight:bold;font-size:11px;">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = "Statut"

    actions = ["manual_withdraw_action", "refund_payments_action"]

    @transaction.atomic
    def manual_withdraw_action(self, request, queryset):
        """
        Action personnalisée pour déclencher un retrait vers PayDunya
        à partir d'un paiement sélectionné (uniquement ceux en attente).
        """
        service = PaymentService()
        count = 0
        for payment in queryset.filter(payment_type="admin_withdraw", status="pending"):
            try:
                # relancer le payout (utilisation du numéro de téléphone stocké en metadata)
                phone = payment.metadata.get("phone_number")
                if phone:
                    service.admin_withdraw(payment.amount, phone)
                    count += 1
            except Exception as e:
                self.message_user(request, f"Échec pour {payment.id}: {e}", level="ERROR")
        self.message_user(request, f"{count} retrait(s) effectué(s).")

    manual_withdraw_action.short_description = "Effectuer le retrait PayDunya sélectionné"

    @transaction.atomic
    def refund_payments_action(self, request, queryset):
        """
        Rembourse manuellement les paiements réussis sélectionnés vers le wallet de l'utilisateur.
        """
        service = PaymentService()
        count = 0

        for payment in queryset.filter(status="success"):
            if not payment.order:
                self.message_user(request, f"Échec pour {payment.id}: Aucune commande associée.", level="ERROR")
                continue

            try:
                refunds = service.refund_order(payment.order, description="Remboursement manuel via Admin")
                if refunds:
                    count += len(refunds)
            except Exception as e:
                self.message_user(request, f"Échec pour {payment.id}: {e}", level="ERROR")

        self.message_user(request, f"{count} paiement(s) remboursé(s) avec succès sur les wallets utilisateurs.")

    refund_payments_action.short_description = "Rembourser les paiements (Wallet)"


@admin.register(GlobalTransaction)
class GlobalTransactionAdmin(admin.ModelAdmin):
    list_display = ("id", "user_link", "payment_type", "provider", "amount", "status_badge", "created_at")
    list_filter = ("payment_type", "provider", "status", "created_at")
    search_fields = ("reference_externe", "user__email", "order__reference")
    autocomplete_fields = ("user", "order")
    readonly_fields = ("id", "created_at", "updated_at", "metadata")
    date_hierarchy = "created_at"
    list_per_page = 25

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("user", "order")

    def user_link(self, obj):
        if obj.user:
            return format_html('<span style="font-weight:bold;">{}</span>', obj.user.email)
        return "-"
    user_link.short_description = "Utilisateur"
    user_link.admin_order_field = "user__email"

    def status_badge(self, obj):
        colors = {'pending': '#f57c00', 'successful': '#388e3c', 'success': '#388e3c', 'failed': '#d32f2f', 'refunded': '#455a64'}
        color = colors.get(obj.status, '#999')
        return format_html(
            '<span style="background:{};color:white;padding:4px 10px;border-radius:6px;font-weight:bold;font-size:11px;">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = "Statut"
    status_badge.admin_order_field = "status"

    # Remove actions that don't make sense for a purely global read-only view
    actions = None
