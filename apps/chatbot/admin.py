"""
Administration Django du module Chatbot IA.

Enregistre les modèles Conversation et Message dans l'interface d'administration
pour permettre à l'équipe de modérer et auditer les échanges.

@module apps.chatbot.admin
"""
from django.contrib import admin

from .models import Conversation, Message


# ============================================================
#  INLINE : Messages dans une Conversation
# ============================================================

class MessageInline(admin.TabularInline):
    """
    Affiche les messages d'une conversation directement dans la vue conversation.
    En lecture seule pour préserver l'intégrité des échanges.
    """

    model = Message
    extra = 0
    readonly_fields = ("id", "role", "content", "created_at")
    fields = ("role", "content", "created_at")
    ordering = ("created_at",)
    can_delete = False

    def has_add_permission(self, request, obj=None) -> bool:
        return False


# ============================================================
#  CONVERSATION
# ============================================================

@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    """
    Administration des conversations chatbot.
    Permet de consulter et modérer les échanges utilisateurs.
    """

    list_display = ("id_short", "user_email", "message_count", "is_active", "created_at")
    list_filter = ("is_active", "created_at")
    search_fields = ("user__email", "id")
    readonly_fields = ("id", "created_at", "updated_at")
    ordering = ("-created_at",)
    inlines = [MessageInline]

    def id_short(self, obj: Conversation) -> str:
        """Affiche les 8 premiers caractères de l'UUID."""
        return str(obj.id)[:8]
    id_short.short_description = "ID"

    def user_email(self, obj: Conversation) -> str:
        """Retourne l'email de l'utilisateur ou 'Anonyme'."""
        return obj.user.email if obj.user else "Anonyme"
    user_email.short_description = "Utilisateur"

    def message_count(self, obj: Conversation) -> int:
        """Retourne le nombre de messages dans la conversation."""
        return obj.messages.count()
    message_count.short_description = "Messages"


# ============================================================
#  MESSAGE
# ============================================================

@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    """
    Administration des messages chatbot.
    Vue en lecture seule pour l'audit des échanges.
    """

    list_display = ("id_short", "conversation_short", "role", "content_preview", "created_at")
    list_filter = ("role", "created_at")
    search_fields = ("content", "conversation__user__email")
    readonly_fields = ("id", "conversation", "role", "content", "created_at", "updated_at")
    ordering = ("-created_at",)

    def id_short(self, obj: Message) -> str:
        return str(obj.id)[:8]
    id_short.short_description = "ID"

    def conversation_short(self, obj: Message) -> str:
        return str(obj.conversation.id)[:8]
    conversation_short.short_description = "Conversation"

    def content_preview(self, obj: Message) -> str:
        """Affiche les 80 premiers caractères du message."""
        return obj.content[:80] + "..." if len(obj.content) > 80 else obj.content
    content_preview.short_description = "Contenu"

    def has_add_permission(self, request) -> bool:
        return False

    def has_change_permission(self, request, obj=None) -> bool:
        return False
