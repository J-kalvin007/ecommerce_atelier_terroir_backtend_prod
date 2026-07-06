from __future__ import annotations

import typing

from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

if typing.TYPE_CHECKING:
    from allauth.socialaccount.models import SocialLogin
    from django.http import HttpRequest

    from ecommerce_backend.users.models import User


class AccountAdapter(DefaultAccountAdapter):
    def is_open_for_signup(self, request: HttpRequest) -> bool:
        return getattr(settings, "ACCOUNT_ALLOW_REGISTRATION", True)

    def get_email_confirmation_url(self, request: HttpRequest, emailconfirmation) -> str:
        """
        Génère l'URL de vérification d'email pointant vers le frontend.
        """
        frontend_url = getattr(settings, "FRONTEND_URL", "http://localhost:3000")
        return f"{frontend_url}/auth/verify-email?key={emailconfirmation.key}"

    def send_mail(self, template_prefix: str, email: str, context: dict) -> None:
        """
        Override pour envoyer des emails HTML premium Atelier du Terroir.
        """
        # Subject
        subject = render_to_string(f"{template_prefix}_subject.txt", context)
        subject = " ".join(subject.splitlines()).strip()

        # Plain text body
        txt_template = f"{template_prefix}_message.txt"
        text_body = render_to_string(txt_template, context)

        # HTML body (facultatif — fallback sur text si le template n'existe pas)
        html_body = None
        try:
            html_template = f"{template_prefix}_message.html"
            html_body = render_to_string(html_template, context)
        except Exception:
            pass

        from_email = getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@atelierduterroir.com")
        msg = EmailMultiAlternatives(subject, text_body, from_email, [email])
        if html_body:
            msg.attach_alternative(html_body, "text/html")
        msg.send()


class SocialAccountAdapter(DefaultSocialAccountAdapter):
    def is_open_for_signup(
        self,
        request: HttpRequest,
        sociallogin: SocialLogin,
    ) -> bool:
        return getattr(settings, "ACCOUNT_ALLOW_REGISTRATION", True)

    def populate_user(
        self,
        request: HttpRequest,
        sociallogin: SocialLogin,
        data: dict[str, typing.Any],
    ) -> User:
        """
        Populates user information from social provider info.

        See: https://docs.allauth.org/en/latest/socialaccount/advanced.html#creating-and-populating-user-instances
        """
        user = super().populate_user(request, sociallogin, data)
        if not user.name:
            if name := data.get("name"):
                user.name = name
            elif first_name := data.get("first_name"):
                user.name = first_name
                if last_name := data.get("last_name"):
                    user.name += f" {last_name}"
        return user
