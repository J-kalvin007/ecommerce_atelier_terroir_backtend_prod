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