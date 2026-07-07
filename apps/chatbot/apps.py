"""
Configuration de l'application Chatbot IA.

Enregistre l'application Django et importe les signaux au démarrage.

@module apps.chatbot.apps
"""
from django.apps import AppConfig


class ChatbotConfig(AppConfig):
    """Configuration de l'application Chatbot IA."""

    name = "apps.chatbot"
    verbose_name = "Chatbot IA"

    def ready(self) -> None:
        """Importe les signaux au démarrage de l'application."""
        # Pas de signaux pour l'instant, mais le hook est en place
        # pour une future extension.
        pass
