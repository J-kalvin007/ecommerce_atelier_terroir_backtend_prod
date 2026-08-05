import django_filters
from .models import Delivery, Livreur

class DeliveryFilter(django_filters.FilterSet):
    order_reference = django_filters.CharFilter(
        field_name="order__reference", lookup_expr="icontains"
    )
    status = django_filters.ChoiceFilter(choices=Delivery.status.field.choices)

    class Meta:
        model = Delivery
        fields = ["status", "order_reference", "delivery_person"]


# ─────────────────────────────────────────────────────────────────────────────
# LIVREUR FILTER
# ─────────────────────────────────────────────────────────────────────────────

class LivreurFilter(django_filters.FilterSet):
    """
    Filtres pour la liste des livreurs (admin uniquement).

    - is_active : filtre sur le statut actif/inactif.
    - type_vehicule : filtre exact sur le type de véhicule.
    - zone_livraison : recherche partielle insensible à la casse.
    """

    is_active = django_filters.BooleanFilter(
        field_name="is_active",
        label="Actif",
    )

    type_vehicule = django_filters.CharFilter(
        field_name="type_vehicule",
        lookup_expr="exact",
        label="Type de véhicule",
    )

    zone_livraison = django_filters.CharFilter(
        field_name="zone_livraison",
        lookup_expr="icontains",
        label="Zone de livraison",
    )

    class Meta:
        model = Livreur
        fields = ["is_active", "type_vehicule", "zone_livraison"]
