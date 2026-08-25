"""
Tests du module promotions.

Couvre :
  - 05 : décrémentation d'un pack — chaque variante composant le pack n'est
         décrémentée qu'une seule fois (variante ET produit synchronisé).
  - 06 : garde-fou anti-rejeu des codes promo (modèle PromoUsage rétabli) et
         présence de l'exception PromoQuotaExceededError.
"""
from decimal import Decimal

import pytest

from apps.catalog.models import Category, Product, ProductVariant
from apps.commandes.models import Order, OrderStatus
from apps.promotions.exceptions import (
    PromoQuotaExceededError,
    PromoUserQuotaExceededError,
)
from apps.promotions.models import Pack, PackItem, PromoCode, PromoUsage
from apps.promotions.services import PackService, PromoService
from ecommerce_backend.users.models import User


@pytest.fixture
def customer(db):
    return User.objects.create_user(
        email="fidele@example.com",
        password="motdepasse-solide-123",
        role=User.UserRole.CUSTOMER,
    )


@pytest.fixture
def product(db):
    category = Category.objects.create(name="Épicerie")
    return Product.objects.create(
        category=category,
        name="Thé",
        sku="THE-001",
        product_type=Product.ProductType.RAW,
        price=Decimal("1500.00"),
        stock=40,
    )


@pytest.fixture
def pack(db, product):
    variant = ProductVariant.objects.filter(product=product).first()
    pack = Pack.objects.create(name="Pack Découverte", price=Decimal("2500.00"))
    PackItem.objects.create(pack=pack, product_variant=variant, quantity=2)
    return pack


# ── Finding 05 : stock du pack ────────────────────────────────────────────────

@pytest.mark.django_db
def test_decrement_pack_stock_ne_decremente_qu_une_fois(pack, product):
    variant = ProductVariant.objects.filter(product=product).first()
    stock_variant_avant = variant.stock
    product.refresh_from_db()
    stock_produit_avant = product.stock

    # 1 pack contenant 2 unités de la variante → -2 attendu, pas -4 ni -6.
    PackService.decrement_pack_stock(pack, requested_quantity=1)

    variant.refresh_from_db()
    product.refresh_from_db()
    assert variant.stock == stock_variant_avant - 2
    assert product.stock == stock_produit_avant - 2


# ── Finding 06 : garde-fou codes promo ────────────────────────────────────────

@pytest.mark.django_db
def test_promo_quota_exceeded_error_est_definie():
    # Simple garantie de non-régression : l'exception référencée par le service
    # existe et est instanciable (elle levait NameError auparavant).
    exc = PromoQuotaExceededError()
    assert exc.code == "promo_quota_exceeded"


@pytest.mark.django_db
def test_un_code_promo_ne_peut_etre_utilise_deux_fois_par_utilisateur(customer):
    promo = PromoCode.objects.create(
        code="BIENVENUE10",
        type=PromoCode.DiscountType.PERCENTAGE,
        value=Decimal("10.00"),
    )
    order1 = Order.objects.create(
        user=customer,
        address_livraison="1 rue du Test",
        phone_livraison="+221770000000",
        city="Dakar",
        country="Sénégal",
        items_total=Decimal("1000.00"),
        total_final=Decimal("1000.00"),
        status=OrderStatus.PENDING_PAYMENT,
    )

    PromoService.apply_code(
        promo_code=promo, user=customer, order=order1, discount_amount=Decimal("100.00"),
    )
    assert PromoUsage.objects.filter(promo_code=promo, user=customer).count() == 1

    # La revalidation refuse désormais le second usage.
    with pytest.raises(PromoUserQuotaExceededError):
        PromoService.validate_code(
            code="BIENVENUE10", user=customer, cart_total=Decimal("1000.00"),
        )
