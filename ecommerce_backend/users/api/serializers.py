from rest_framework import serializers

from ecommerce_backend.users.models import User


class UserSerializer(serializers.ModelSerializer):

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "name",
            "role",
            "phone_number",
            "profile_image",
            "is_active",
            "is_verified",
            "created_at",
            "updated_at",
        ]
        # SÉCURITÉ — Escalade de privilèges.
        # `role`, `is_active` et `is_verified` déterminent les droits d'accès de
        # l'utilisateur (IsPlatformAdmin, IsCustomer, authentification). Sans cette
        # liste, un client authentifié pouvait s'auto-promouvoir administrateur via
        # PATCH /api/users/<son-id>/ avec {"role": "platform_admin"}.
        # Ces champs restent exposés en lecture mais ne sont JAMAIS modifiables
        # par l'API ; leur attribution relève de l'administration Django.
        read_only_fields = [
            "id",
            "role",
            "is_active",
            "is_verified",
            "created_at",
            "updated_at",
        ]
