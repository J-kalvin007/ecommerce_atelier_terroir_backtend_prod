"""
Modèles du module Chatbot IA.

Deux entités principales :
- Conversation : session de discussion liée à un utilisateur (nullable pour les anonymes).
- Message      : chaque échange au sein d'une conversation (rôle user ou assistant).

Ces deux modèles héritent de BaseModel pour bénéficier de :
- UUID comme clé primaire
- Champs `created_at`, `updated_at`, `is_active` automatiques

@module apps.chatbot.models
"""
from django.conf import settings
from django.db import models

from apps.core.models import BaseModel


# ============================================================
#  CONVERSATION
# ============================================================

class Conversation(BaseModel):
    """
    Session de conversation entre un utilisateur et l'assistant IA.

    Une conversation regroupe une série de messages ordonnés chronologiquement.
    Elle peut être anonyme (`user=None`) pour les visiteurs non connectés,
    auquel cas l'historique n'est pas persisté côté serveur.

    Attributes:
        user      : Utilisateur connecté (null si anonyme).
        is_active : Hérité de BaseModel — permet de "archiver" une conversation.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="chatbot_conversations",
        null=True,
        blank=True,
        verbose_name="Utilisateur",
        help_text="Null pour les visiteurs anonymes.",
    )

    class Meta:
        db_table = "chatbot_conversations"
        verbose_name = "Conversation"
        verbose_name_plural = "Conversations"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"]),
        ]

    def __str__(self) -> str:
        user_label = self.user.email if self.user else "Anonyme"
        return f"Conversation {str(self.id)[:8]} — {user_label}"


# ============================================================
#  MESSAGE
# ============================================================

class Message(BaseModel):
    """
    Message individuel au sein d'une conversation.

    Chaque échange (question utilisateur et réponse de l'assistant)
    est enregistré comme un Message distinct avec un rôle explicite.

    Attributes:
        conversation : La conversation parente.
        role         : 'user' (message du client) ou 'assistant' (réponse IA).
        content      : Texte brut du message.

    Note:
        L'historique envoyé au LLM est limité aux 10 derniers messages
        de la conversation (voir ChatService._build_context).
    """

    class Role(models.TextChoices):
        USER = "user", "Utilisateur"
        ASSISTANT = "assistant", "Assistant IA"

    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name="messages",
        verbose_name="Conversation",
    )

    role = models.CharField(
        max_length=10,
        choices=Role.choices,
        verbose_name="Rôle",
        help_text="'user' pour les messages du client, 'assistant' pour les réponses IA.",
    )

    content = models.TextField(
        verbose_name="Contenu",
        help_text="Texte brut du message.",
    )

    class Meta:
        db_table = "chatbot_messages"
        verbose_name = "Message"
        verbose_name_plural = "Messages"
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["conversation", "created_at"]),
        ]

    def __str__(self) -> str:
        preview = self.content[:60] + "..." if len(self.content) > 60 else self.content
        return f"[{self.role}] {preview}"
