
from dj_rest_auth.registration.serializers import RegisterSerializer
from rest_framework import serializers
from .models import User
from dj_rest_auth.serializers import LoginSerializer, PasswordResetSerializer
from .utils import password_reset_url_generator


class CustomRegisterSerializer(RegisterSerializer):
    username = None
    
    name = serializers.CharField(
        max_length=100,
        required=False
    )

    def get_cleaned_data(self):
        data = super().get_cleaned_data()

        data["name"] = self.validated_data.get("name", "")

        return data

    def save(self, request):
        user = super().save(request)

        user.name = self.validated_data["name"]

        user.save(update_fields=["name"])

        return user






class UserSerializer(serializers.ModelSerializer):

    class Meta:
        model = User

        fields = (
            "id",
            "email",
            "name",
            "role",
            "phone_number",
            "profile_image",
            "is_active",
            "is_verified",
        )




class CustomLoginSerializer(LoginSerializer):
    pass

class CustomPasswordResetSerializer(PasswordResetSerializer):
    def get_email_options(self):
        return {
            'url_generator': password_reset_url_generator,
            'email_template_name': 'account/email/password_reset_key_message.txt',
            'html_email_template_name': 'account/email/password_reset_key_message.html',
            'subject_template_name': 'account/email/password_reset_key_subject.txt',
        }