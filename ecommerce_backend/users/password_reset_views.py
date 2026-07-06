"""
Custom Password Reset Confirm View — Bypass dj-rest-auth

PROBLÈME RÉSOLU :
    dj-rest-auth + allauth utilisent 'user_pk_to_url_str(user)' pour encoder l'uid
    dans les emails, mais leur PasswordResetConfirmSerializer tente de valider via
    allauth, ce qui crée une incohérence selon la configuration.

    Cette vue bypasse complètement dj-rest-auth et utilise directement :
      - urlsafe_base64_decode pour décoder l'uid (cohérent avec utils.py)
      - default_token_generator.check_token pour valider le token Django
      - SetPasswordForm pour la validation des mots de passe

ENDPOINT : POST /api/auth/password/reset/confirm/
PAYLOAD  : { uid, token, new_password1, new_password2 }
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.forms import SetPasswordForm
from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode

from rest_framework import serializers, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from drf_spectacular.utils import extend_schema, OpenApiResponse

User = get_user_model()


class PasswordResetConfirmSerializer(serializers.Serializer):
    """
    Sérialiseur de validation pour la confirmation de réinitialisation de mot de passe.
    Utilise le décodage base64url standard Django, cohérent avec utils.py.
    """
    uid = serializers.CharField(write_only=True)
    token = serializers.CharField(write_only=True)
    new_password1 = serializers.CharField(
        style={"input_type": "password"},
        write_only=True,
        min_length=8,
    )
    new_password2 = serializers.CharField(
        style={"input_type": "password"},
        write_only=True,
        min_length=8,
    )

    def validate(self, attrs):
        uid_encoded = attrs.get("uid")
        token = attrs.get("token")
        new_password1 = attrs.get("new_password1")
        new_password2 = attrs.get("new_password2")

        # Vérification de la correspondance des mots de passe
        if new_password1 != new_password2:
            raise serializers.ValidationError(
                {"new_password2": "Les deux mots de passe ne correspondent pas."}
            )

        # Décodage de l'uid
        try:
            uid = force_str(urlsafe_base64_decode(uid_encoded))
            user = User.objects.get(pk=uid)
        except (User.DoesNotExist, ValueError, TypeError, OverflowError):
            raise serializers.ValidationError(
                {"uid": "L'identifiant de compte est invalide ou introuvable."}
            )

        # Validation du token via le générateur Django
        if not default_token_generator.check_token(user, token):
            raise serializers.ValidationError(
                {
                    "token": (
                        "Le lien de réinitialisation est invalide ou a expiré. "
                        "Chaque lien ne peut être utilisé qu'une seule fois."
                    )
                }
            )

        # Validation des mots de passe via SetPasswordForm Django
        form = SetPasswordForm(user=user, data={
            "new_password1": new_password1,
            "new_password2": new_password2,
        })
        if not form.is_valid():
            raise serializers.ValidationError(form.errors)

        attrs["user"] = user
        attrs["form"] = form
        return attrs


class CustomPasswordResetConfirmView(APIView):
    """
    Vue de confirmation de réinitialisation de mot de passe.

    Bypasse dj-rest-auth/allauth pour utiliser directement la validation Django,
    assurant une compatibilité parfaite avec le générateur d'URL dans utils.py.

    POST /api/auth/password/reset/confirm/
    {
        "uid": "<base64url encoded user pk>",
        "token": "<reset token>",
        "new_password1": "<nouveau mot de passe>",
        "new_password2": "<confirmation du mot de passe>"
    }
    """
    permission_classes = [AllowAny]
    serializer_class = PasswordResetConfirmSerializer

    @extend_schema(
        summary="Confirmer la réinitialisation du mot de passe",
        description=(
            "Valide le token de réinitialisation et met à jour le mot de passe. "
            "L'uid et le token proviennent du lien reçu par email. "
            "Chaque lien est utilisable une seule fois."
        ),
        request=PasswordResetConfirmSerializer,
        responses={
            200: OpenApiResponse(description="Mot de passe mis à jour avec succès."),
            400: OpenApiResponse(description="Token invalide, expiré, ou mots de passe non conformes."),
        },
        tags=["Auth"],
    )
    def post(self, request, *args, **kwargs):
        serializer = PasswordResetConfirmSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # Sauvegarde du nouveau mot de passe
        form = serializer.validated_data["form"]
        form.save()

        return Response(
            {"detail": "Mot de passe réinitialisé avec succès."},
            status=status.HTTP_200_OK,
        )
