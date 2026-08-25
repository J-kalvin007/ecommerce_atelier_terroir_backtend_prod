"""
Tests d'intégrité et de contrôle d'accès du module commandes.

Couvre :
  - 03 : IDOR — le détail/l'historique d'une commande rattachée à un compte
         n'est lisible que par son propriétaire (ou un admin).
  - 05 : le stock d'un produit est décrémenté UNE seule fois par commande.
"""
from decimal import Decimal

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.catalog.models import Category, Product, ProductVariant
from apps.commandes.models import Order, OrderStatus
from apps.commandes.services import OrderService
from ecommerce_backend.users.models import User


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def customer(db):
    return User.objects.create_user(
        email="proprio@example.com",
        password="motdepasse-solide-123",
        role=User.UserRole.CUSTOMER,
    )


@pytest.fixture
def intruder(db):
    return User.objects.create_user(
        email="intrus@example.com",
        password="motdepasse-solide-123",
        role=User.UserRole.CUSTOMER,
    )


@pytest.fixture
def product(db):
    category = Category.objects.create(name="Épicerie")
    # Le signal post_save crée automatiquement la variante par défaut.
    return Product.objects.create(
        category=category,
        name="Café",
        sku="CAFE-001",
        product_type=Product.ProductType.RAW,
        price=Decimal("2000.00"),
        stock=100,
    )


@pytest.fixture
def order(db, customer):
    return Order.objects.create(
        user=customer,
        address_livraison="1 rue du Test",
        phone_livraison="+221770000000",
        city="Dakar",
        country="Sénégal",
        items_total=Decimal("2000.00"),
        total_final=Decimal("2000.00"),
        status=OrderStatus.PENDING_PAYMENT,
    )


# ── Finding 03 : IDOR ─────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_detail_commande_d_autrui_est_refuse(api_client, order, intruder):
    api_client.force_authenticate(user=intruder)
    resp = api_client.get(
        reverse("commandes:order-detail", kwargs={"reference": str(order.id)}),
    )
    assert resp.status_code == 403


@pytest.mark.django_db
def test_detail_commande_par_le_proprietaire_est_autorise(api_client, order, customer):
    api_client.force_authenticate(user=customer)
    resp = api_client.get(
        reverse("commandes:order-detail", kwargs={"reference": str(order.id)}),
    )
    assert resp.status_code == 200


@pytest.mark.django_db
def test_historique_commande_d_autrui_est_refuse(api_client, order, intruder):
    api_client.force_authenticate(user=intruder)
    resp = api_client.get(
        reverse("commandes:order-history", kwargs={"reference": str(order.id)}),
    )
    assert resp.status_code == 403


# ── Finding 05 : stock décrémenté une seule fois ──────────────────────────────

@pytest.mark.django_db
def test_create_order_decremente_le_stock_une_seule_fois(customer, product):
    variant = ProductVariant.objects.filter(product=product).first()
    stock_variant_avant = variant.stock
    product.refresh_from_db()
    stock_produit_avant = product.stock

    OrderService.create_order(
        user=customer,
        items=[{"product_id": str(variant.id), "quantity": 3}],
        address_livraison="1 rue du Test",
        phone_livraison="+221770000000",
        city="Dakar",
        country="Sénégal",
    )

    variant.refresh_from_db()
    product.refresh_from_db()

    # Exactement -3 sur la variante ET sur le produit (le produit est synchronisé
    # par le signal, pas re-décrémenté indépendamment).
    assert variant.stock == stock_variant_avant - 3
    assert product.stock == stock_produit_avant - 3
