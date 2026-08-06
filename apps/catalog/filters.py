from django_filters.rest_framework import (
    BooleanFilter,
    CharFilter,
    FilterSet,
    NumberFilter,
)

from .models import Product


class ProductFilter(FilterSet):

    min_price = NumberFilter(
        field_name="price",
        lookup_expr="gte",
    )

    max_price = NumberFilter(
        field_name="price",
        lookup_expr="lte",
    )

    category = CharFilter(
        field_name="category__slug",
    )

    product_type = CharFilter(
        field_name="product_type",
    )

    slug = CharFilter(
        field_name="slug",
    )

    sku = CharFilter(
        field_name="sku",
    )

    is_top = BooleanFilter(
        field_name="is_top",
    )

    min_stock = NumberFilter(
        field_name="stock",
        lookup_expr="gte",
        help_text="Stock supérieur ou égal à",
    )

    max_stock = NumberFilter(
        field_name="stock",
        lookup_expr="lte",
        help_text="Stock inférieur ou égal à",
    )

    stock = NumberFilter(
        field_name="stock",
        help_text="Stock exact",
    )

    class Meta:
        model = Product

        fields = [
            "category",
            "product_type",
            "is_top",
        ]