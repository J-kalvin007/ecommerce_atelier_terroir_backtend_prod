from django.conf import settings
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes


def password_reset_url_generator(request, user, temp_key):
    """
    Génère l'URL de réinitialisation de mot de passe qui pointe vers le frontend Next.js.

    IMPORTANT : On utilise urlsafe_base64_encode(force_bytes(user.pk)) pour l'uid car
    la vue CustomPasswordResetConfirmView decode l'uid avec urlsafe_base64_decode,
    ce qui est aligné avec le SetPasswordForm de Django standard.
    """
    frontend_url = getattr(settings, "FRONTEND_URL", "https://atelierterroirsolime.vercel.app")

    # Encodage base64url standard Django — cohérent avec CustomPasswordResetConfirmView
    uid = urlsafe_base64_encode(force_bytes(user.pk))

    return f"{frontend_url}/auth/password-reset/confirm/{uid}/{temp_key}"

