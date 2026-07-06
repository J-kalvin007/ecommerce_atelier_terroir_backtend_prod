from django.shortcuts import get_object_or_404

from apps.commandes.models import Order


class OrderSelector:
    @staticmethod
    def get_user_orders(user):
        return Order.objects.filter(
            user=user,
            is_active=True,
        ).order_by("-created_at")

    @staticmethod
    def get_user_order_by_reference(*, user, reference):
        return get_object_or_404(
            Order.objects.prefetch_related(
                "items",
                "status_history",
            ),
            user=user,
            reference=reference,
            is_active=True,
        )

    @staticmethod
    def get_order_history(*, user, reference):
        order = OrderSelector.get_user_order_by_reference(
            user=user,
            reference=reference,
        )
        return order.status_history.all().order_by("created_at")

    @staticmethod
    def get_admin_orders():
        return Order.objects.all().select_related("user").order_by("-created_at")

    @staticmethod
    def get_admin_order_by_reference(reference):
        return get_object_or_404(
            Order.objects.prefetch_related(
                "items",
                "status_history",
            ),
            reference=reference,
        )