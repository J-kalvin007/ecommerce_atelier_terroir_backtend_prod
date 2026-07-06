import django_filters

from apps.commandes.models import Order


class OrderFilter(django_filters.FilterSet):
    reference = django_filters.CharFilter(
        field_name="reference",
        lookup_expr="icontains",
    )
    status = django_filters.CharFilter(
        field_name="status",
    )
    created_after = django_filters.DateFilter(
        field_name="created_at",
        lookup_expr="gte",
    )
    created_before = django_filters.DateFilter(
        field_name="created_at",
        lookup_expr="lte",
    )

    class Meta:
        model = Order
        fields = (
            "reference",
            "status",
        )