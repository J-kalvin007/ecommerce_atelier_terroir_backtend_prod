"""
Sérialiseurs DRF du module Chatbot IA.

Quatre sérialiseurs :
- ChatRequestSerializer      : Validation du message chat.
- ChatResponseSerializer     : Structure de la réponse chat.
- AISearchRequestSerializer  : Validation de la requête de recherche IA.
- AISearchResponseSerializer : Structure de la réponse de recherche IA.
- RecommendationRequestSerializer  : Validation de la requête de recommandations.
- RecommendationResponseSerializer : Structure de la réponse de recommandations.

@module apps.chatbot.serializers
"""
import uuid

from rest_framework import serializers


# ============================================================
#  CHAT — REQUÊTE / RÉPONSE
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


# ============================================================
#  AI SEARCH — REQUÊTE / RÉPONSE
# ============================================================

class AISearchRequestSerializer(serializers.Serializer):
    """
    Valide la requête de recherche intelligente IA.

    Champs :
        query           : Texte libre de recherche (obligatoire, max 500 caractères).
        conversation_id : UUID de la conversation à poursuivre (optionnel).
    """

    query = serializers.CharField(
        max_length=500,
        trim_whitespace=True,
        error_messages={
            "blank": "La requête de recherche ne peut pas être vide.",
            "max_length": "La requête ne peut pas dépasser 500 caractères.",
        },
    )

    conversation_id = serializers.UUIDField(
        required=False,
        allow_null=True,
        default=None,
    )


class AISearchResponseSerializer(serializers.Serializer):
    """
    Structure de la réponse de la recherche IA.

    Champs :
        message         : Réponse formatée par le LLM.
        results_count   : Nombre total d'éléments trouvés.
        role            : Rôle de l'utilisateur (anonymous / customer / platform_admin).
    """

    message = serializers.CharField(
        help_text="Réponse formatée par l'assistant IA.",
    )

    results_count = serializers.IntegerField(
        default=0,
        help_text="Nombre d'éléments trouvés.",
    )

    role = serializers.CharField(
        default="anonymous",
        help_text="Rôle de l'utilisateur pour la session.",
    )


# ============================================================
#  RECOMMENDATIONS — REQUÊTE / RÉPONSE
# ============================================================

class RecommendationProductInputSerializer(serializers.Serializer):
    """Produit minimal envoyé par le frontend pour le contexte."""
    id = serializers.CharField()
    name = serializers.CharField()
    category = serializers.CharField(required=False, allow_blank=True, default="")
    price = serializers.FloatField(required=False, allow_null=True, default=None)


class RecommendationSuggestionSerializer(serializers.Serializer):
    """Une suggestion de produit retournée par le service."""
    product = serializers.DictField(help_text="Les infos de base du produit recommandé")
    reason = serializers.CharField()
    score = serializers.FloatField(required=False, allow_null=True)


class RecommendationRequestSerializer(serializers.Serializer):
    """
    Valide la requête de recommandations IA.

    Champs :
        products         : Catalogue produits visible côté client (optionnel).
        cart_items       : IDs des produits dans le panier (optionnel).
        viewed_categories: Catégories récemment consultées (optionnel).
        user_intent      : Intention utilisateur libre (optionnel).
        conversation_id  : UUID de la conversation (optionnel).
    """

    products = RecommendationProductInputSerializer(
        many=True,
        required=False,
        default=list,
    )

    cart_items = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        default=list,
    )

    viewed_categories = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        default=list,
    )

    user_intent = serializers.CharField(
        required=False,
        allow_blank=True,
        default="",
    )

    conversation_id = serializers.UUIDField(
        required=False,
        allow_null=True,
        default=None,
    )


class RecommendationResponseSerializer(serializers.Serializer):
    """Structure de la réponse des recommandations."""

    suggestions = RecommendationSuggestionSerializer(many=True)

    conversation_id = serializers.UUIDField(
        required=False,
        allow_null=True,
        default=None,
    )

