"""
Test de non-régression du finding 01 : élévation de privilèges.

Un client authentifié ne doit jamais pouvoir modifier son propre `role`,
`is_active` ou `is_verified` via l'API. Ces champs restent lisibles mais sont
strictement en lecture seule.
"""
import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from ecommerce_backend.users.models import User


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def customer(db):
    return User.objects.create_user(
        email="ambitieux@example.com",
        password="motdepasse-solide-123",
        role=User.UserRole.CUSTOMER,
    )


@pytest.mark.django_db
def test_un_client_ne_peut_pas_s_auto_promouvoir_admin(api_client, customer):
    api_client.force_authenticate(user=customer)
    resp = api_client.patch(
        reverse("api:user-detail", kwargs={"pk": customer.pk}),
        data={
            "role": "platform_admin",
            "is_active": True,
            "is_verified": True,
            "name": "Nom modifié",
        },
        format="json",
    )

    assert resp.status_code == 200
    customer.refresh_from_db()
    # Le champ éditable a bien changé…
    assert customer.name == "Nom modifié"
    # …mais aucun champ de privilège n'a bougé.
    assert customer.role == User.UserRole.CUSTOMER
    assert customer.is_verified is False


@pytest.mark.django_db
def test_role_est_expose_en_lecture(api_client, customer):
    api_client.force_authenticate(user=customer)
    resp = api_client.get(reverse("api:user-detail", kwargs={"pk": customer.pk}))
    assert resp.status_code == 200
    assert resp.data["role"] == User.UserRole.CUSTOMER
