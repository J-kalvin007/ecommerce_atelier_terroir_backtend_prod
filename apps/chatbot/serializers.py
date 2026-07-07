"""
Sérialiseurs DRF du module Chatbot IA.

Deux sérialiseurs :
- ChatRequestSerializer  : Validation et désérialisation de la requête entrante.
- ChatResponseSerializer : Structure de la réponse retournée au frontend.

@module apps.chatbot.serializers
"""
import uuid

from rest_framework import serializers


# ============================================================
#  REQUÊTE
# ============================================================

class ChatRequestSerializer(serializers.Serializer):
    """
    Valide la requête POST envoyée par le frontend au chatbot.

    Champs :
        message         : Texte du message de l'utilisateur (obligatoire).
        conversation_id : UUID de la conversation à poursuivre (optionnel).
                          Si absent ou invalide, une nouvelle conversation est créée.
    """

    message = serializers.CharField(
        max_length=2000,
        trim_whitespace=True,
        error_messages={
            "blank": "Le message ne peut pas être vide.",
            "max_length": "Le message ne peut pas dépasser 2000 caractères.",
        },
    )

    conversation_id = serializers.UUIDField(
        required=False,
        allow_null=True,
        default=None,
        help_text="UUID de la conversation existante à poursuivre. Null pour en démarrer une nouvelle.",
    )


# ============================================================
#  RÉPONSE
# ============================================================

class ChatResponseSerializer(serializers.Serializer):
    """
    Structure de la réponse renvoyée au frontend après traitement IA.

    Champs :
        message         : Réponse générée par l'assistant IA.
        conversation_id : UUID de la conversation (nouvelle ou existante).
    """

    message = serializers.CharField(
        help_text="Réponse textuelle de l'assistant IA.",
    )

    conversation_id = serializers.UUIDField(
        help_text="UUID de la conversation — à conserver pour les prochains échanges.",
    )
