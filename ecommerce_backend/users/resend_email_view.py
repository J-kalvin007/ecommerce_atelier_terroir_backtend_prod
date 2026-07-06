"""
Vue custom de renvoi d'email de confirmation.

La vue native dj-rest-auth (ResendEmailVerificationView) retourne toujours
{"detail": "ok"} mais le vrai envoi est bloqué par le cooldown d'allauth
(ACCOUNT_RATE_LIMITS / EMAIL_CONFIRMATION_COOLDOWN).

Cette vue bypasse ce cooldown en appelant directement l'adaptateur allauth
pour forcer l'envoi immédiat de l'email de confirmation.
"""

from allauth.account.models import EmailAddress
from allauth.account import app_settings as allauth_settings
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView


class ResendEmailSerializer(serializers.Serializer):
    email = serializers.EmailField()


class ForceResendEmailView(APIView):
    """
    POST /api/auth/registration/force-resend-email/

    Renvoie l'email de confirmation en bypassant le cooldown allauth.
    Retourne toujours 200 (pour ne pas révéler si l'email existe ou non).
    """
    permission_classes = [AllowAny]
    serializer_class = ResendEmailSerializer

    def post(self, request, *args, **kwargs):
        serializer = ResendEmailSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data["email"].lower().strip()

        try:
            email_address = EmailAddress.objects.get(email__iexact=email)
        except EmailAddress.DoesNotExist:
            # On ne révèle pas si l'email existe ou non
            return Response({"detail": "ok"}, status=status.HTTP_200_OK)

        # Si déjà vérifié → on ne renvoie pas
        if email_address.verified:
            return Response(
                {"detail": "Cet email est déjà vérifié."},
                status=status.HTTP_200_OK
            )

        # Envoi direct via allauth sans passer par le rate-limit
        from allauth.account.models import EmailConfirmationHMAC
        from allauth.account.adapter import get_adapter
        
        # On crée la confirmation manuellement
        confirmation = EmailConfirmationHMAC(email_address)
        # On l'envoie via l'adapter
        get_adapter(request).send_confirmation_mail(request, confirmation, signup=False)

        return Response({"detail": "ok"}, status=status.HTTP_200_OK)
