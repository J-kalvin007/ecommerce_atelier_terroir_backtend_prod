import django_filters
from .models import Delivery

class DeliveryFilter(django_filters.FilterSet):
    order_reference = django_filters.CharFilter(
        field_name="order__reference", lookup_expr="icontains"
    )
    status = django_filters.ChoiceFilter(choices=Delivery.status.field.choices)

    class Meta:
        model = Delivery
        fields = ["status", "order_reference", "delivery_person"]
