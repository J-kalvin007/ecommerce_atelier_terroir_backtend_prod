"""
Tests de sécurité et d'intégrité du module de paiement.

Couvre les findings d'audit les plus critiques :
  - 02 : le webhook PayDunya n'accorde jamais confiance au corps du POST ;
         le statut/montant est relu côté serveur via verify_payment.
  - 03 : IDOR — impossible d'initier le paiement de la commande d'autrui.
  - 04 : rejeu de webhook — un token déjà encaissé n'est jamais retraité.
"""
import hashlib
from decimal import Decimal
from unittest import mock

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.catalog.models import Category, Product
from apps.commandes.models import Order, OrderStatus
from apps.paiements.models import Payment, Wallet
from ecommerce_backend.users.models import User


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def customer(db):
    return User.objects.create_user(
        email="client@example.com",
        password="motdepasse-solide-123",
        role=User.UserRole.CUSTOMER,
    )


@pytest.fixture
def other_customer(db):
    return User.objects.create_user(
        email="autre@example.com",
        password="motdepasse-solide-123",
        role=User.UserRole.CUSTOMER,
    )


@pytest.fixture
def product(db):
    category = Category.objects.create(name="Épicerie")
    return Product.objects.create(
        category=category,
        name="Miel",
        sku="MIEL-001",
        product_type=Product.ProductType.RAW,
        price=Decimal("1000.00"),
        stock=50,
    )


@pytest.fixture
def order(db, customer, product):
    return Order.objects.create(
        user=customer,
        address_livraison="1 rue du Test",
        phone_livraison="+221770000000",
        city="Dakar",
        country="Sénégal",
        items_total=Decimal("1000.00"),
        total_final=Decimal("1000.00"),
        status=OrderStatus.PENDING_PAYMENT,
    )


def _valid_master_key_hash(settings):
    master_key = settings.PAYDUNYA_CONFIG["MASTER_KEY"].encode()
    return hashlib.sha512(master_key).hexdigest()


# ── Finding 02 & 04 : webhook PayDunya ────────────────────────────────────────

@pytest.mark.django_db
def test_webhook_rejette_signature_invalide(api_client):
    resp = api_client.post(
        reverse("paydunya_ipn"),
        data={
            "data[invoice][token]": "TOK123",
            "data[status]": "completed",
            "data[hash]": "hash-bidon",
        },
    )
    assert resp.status_code == 403


@pytest.mark.django_db
def test_webhook_ne_valide_pas_sur_le_seul_corps_du_post(api_client, settings, order):
    """
    Le corps annonce 'completed' mais PayDunya répond 'pending' : la commande
    NE doit PAS être marquée payée. Seule la vérification serveur fait foi.
    """
    order.reference = "TOK-PENDING"
    order.save(update_fields=["reference"])

    with mock.patch(
        "apps.paiements.api.views.PayDunyaGateway.verify_payment",
        return_value={"status": "pending", "amount": "1000", "raw": {}},
    ):
        resp = api_client.post(
            reverse("paydunya_ipn"),
            data={
                "data[invoice][token]": "TOK-PENDING",
                "data[status]": "completed",
                "data[invoice][description]": "ACHAT-PRODUIT",
                "data[invoice][total_amount]": "1000",
                "data[hash]": _valid_master_key_hash(settings),
            },
        )

    assert resp.status_code == 200
    order.refresh_from_db()
    assert order.status == OrderStatus.PENDING_PAYMENT
    assert not Payment.objects.filter(reference_externe="TOK-PENDING").exists()


@pytest.mark.django_db
def test_webhook_valide_la_commande_quand_paydunya_confirme(api_client, settings, order):
    order.reference = "TOK-OK"
    order.save(update_fields=["reference"])

    with mock.patch(
        "apps.paiements.api.views.PayDunyaGateway.verify_payment",
        return_value={
            "status": "completed",
            "amount": "1000",
            "raw": {"invoice": {"description": "ACHAT-PRODUIT", "total_amount": "1000"}},
        },
    ):
        resp = api_client.post(
            reverse("paydunya_ipn"),
            data={
                "data[invoice][token]": "TOK-OK",
                "data[status]": "completed",
                "data[invoice][description]": "ACHAT-PRODUIT",
                "data[invoice][total_amount]": "1000",
                "data[hash]": _valid_master_key_hash(settings),
            },
        )

    assert resp.status_code == 200
    order.refresh_from_db()
    assert order.status == OrderStatus.PAID
    assert Payment.objects.filter(
        reference_externe="TOK-OK", status=Payment.Status.SUCCESS,
    ).count() == 1


@pytest.mark.django_db
def test_webhook_est_idempotent_sur_rejeu(api_client, settings, order):
    """Un second callback identique ne crée pas de second Payment."""
    order.reference = "TOK-REPLAY"
    order.save(update_fields=["reference"])

    payload = {
        "data[invoice][token]": "TOK-REPLAY",
        "data[status]": "completed",
        "data[invoice][description]": "ACHAT-PRODUIT",
        "data[invoice][total_amount]": "1000",
        "data[hash]": _valid_master_key_hash(settings),
    }
    verify = {
        "status": "completed",
        "amount": "1000",
        "raw": {"invoice": {"description": "ACHAT-PRODUIT", "total_amount": "1000"}},
    }

    with mock.patch(
        "apps.paiements.api.views.PayDunyaGateway.verify_payment", return_value=verify,
    ):
        first = api_client.post(reverse("paydunya_ipn"), data=payload)
        second = api_client.post(reverse("paydunya_ipn"), data=payload)

    assert first.status_code == 200
    assert second.status_code == 200
    assert Payment.objects.filter(reference_externe="TOK-REPLAY").count() == 1


@pytest.mark.django_db
def test_webhook_refuse_sous_paiement(api_client, settings, order):
    """Un montant encaissé inférieur au total ne valide pas la commande."""
    order.reference = "TOK-UNDERPAID"
    order.save(update_fields=["reference"])

    with mock.patch(
        "apps.paiements.api.views.PayDunyaGateway.verify_payment",
        return_value={
            "status": "completed",
            "amount": "500",  # < total_final 1000
            "raw": {"invoice": {"description": "ACHAT-PRODUIT", "total_amount": "500"}},
        },
    ):
        resp = api_client.post(
            reverse("paydunya_ipn"),
            data={
                "data[invoice][token]": "TOK-UNDERPAID",
                "data[status]": "completed",
                "data[invoice][description]": "ACHAT-PRODUIT",
                "data[invoice][total_amount]": "500",
                "data[hash]": _valid_master_key_hash(settings),
            },
        )

    assert resp.status_code == 400
    order.refresh_from_db()
    assert order.status == OrderStatus.PENDING_PAYMENT


# ── Finding 03 : IDOR sur l'initiation de paiement ────────────────────────────

@pytest.mark.django_db
def test_initier_paiement_commande_d_autrui_est_interdit(
    api_client, order, other_customer,
):
    api_client.force_authenticate(user=other_customer)
    resp = api_client.post(
        reverse("initier-paiement-direct"),
        data={"order_id": str(order.id), "description": "ACHAT-PRODUIT"},
        format="json",
    )
    assert resp.status_code == 403


@pytest.mark.django_db
def test_recharge_wallet_d_autrui_est_interdite(api_client, customer, other_customer):
    # Un wallet est auto-créé par signal à la création de l'utilisateur.
    wallet = Wallet.objects.get(user=customer)
    api_client.force_authenticate(user=other_customer)
    resp = api_client.post(
        reverse("recharge-wallet-direct"),
        data={"order_id": str(wallet.id), "amount": "1000", "description": "RECHARGE-WALLET"},
        format="json",
    )
    assert resp.status_code == 403
