"""
Vues DRF du module Chatbot IA.

Endpoints :
  POST /api/v1/chatbot/chat/           — Conversation IA classique
  POST /api/v1/chatbot/search/         — Recherche intelligente multi-tables avec RBAC
  POST /api/v1/chatbot/recommendations/ — Recommandations personnalisées ORM

@module apps.chatbot.views
"""
import logging

import openai
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework.authentication import SessionAuthentication, TokenAuthentication
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status

from .serializers import (
    ChatRequestSerializer,
    ChatResponseSerializer,
    AISearchRequestSerializer,
    AISearchResponseSerializer,
    RecommendationRequestSerializer,
    RecommendationResponseSerializer,
)
from .services import ChatService
from .search_service import AISearchService
from .recommendation_service import RecommendationService

logger = logging.getLogger(__name__)


# ============================================================
#  CHAT VIEW
# ============================================================

class ChatView(APIView):
    """
    POST /api/v1/chatbot/chat/

    Endpoint principal du chatbot IA.

    - Authentification : optionnelle. Les utilisateurs non connectés peuvent
      accéder aux fonctionnalités publiques (produits, catégories).
      Les fonctionnalités privées (commandes, wallet, fidélité) requièrent
      un token DRF valide dans le header `Authorization: Token <key>`.

    - Permission : AllowAny — la gestion de l'accès est manuelle via
      ChatService qui vérifie `self.user` avant chaque appel API privé.

    Corps de la requête (JSON) :
      {
        "message": "Quels produits bio avez-vous ?",
        "conversation_id": "uuid-de-la-conversation"
      }

    Réponse (JSON) :
      {
        "message": "Nous avons les produits suivants...",
        "conversation_id": "uuid-de-la-conversation"
      }
    """

    authentication_classes = [TokenAuthentication, SessionAuthentication]
    permission_classes = [AllowAny]

    @extend_schema(
        summary="Chatbot IA — Envoyer un message",
        description=(
            "Envoie un message à l'assistant IA de L'Atelier du Terroir. "
            "L'assistant peut répondre en français aux questions sur les produits, "
            "les commandes (si connecté), le wallet (si connecté) et la fidélité (si connecté)."
        ),
        request=ChatRequestSerializer,
        responses={
            200: ChatResponseSerializer,
            400: OpenApiResponse(description="Données de requête invalides."),
            503: OpenApiResponse(description="Service IA temporairement indisponible."),
        },
        tags=["Chatbot IA"],
    )
    def post(self, request: Request) -> Response:
        serializer = ChatRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        user_message: str = serializer.validated_data["message"]
        conversation_id = serializer.validated_data.get("conversation_id")
        user = request.user if request.user.is_authenticated else None

        service = ChatService(user=user)

        try:
            result = service.process_message(
                user_message=user_message,
                conversation_id=conversation_id,
            )
        except openai.AuthenticationError:
            logger.error("ChatView: clé API OpenAI invalide ou non configurée.")
            return Response(
                {"message": "Le service IA n'est pas correctement configuré. Veuillez contacter l'administrateur."},
                status=status.HTTP_200_OK,
            )
        except openai.RateLimitError as exc:
            logger.warning("ChatView: limite de débit OpenAI atteinte. %s", str(exc))
            error_message = "Le service IA est momentanément surchargé. Veuillez réessayer dans quelques instants."
            if "insufficient_quota" in str(exc):
                error_message = "Désolé, le service est temporairement indisponible en raison d'un dépassement de quota (crédits épuisés)."
            return Response({"message": error_message}, status=status.HTTP_200_OK)
        except openai.OpenAIError as exc:
            logger.error("ChatView: erreur OpenAI inattendue — %s", str(exc))
            return Response(
                {"message": "Le chatbot IA est momentanément indisponible suite à une erreur technique. Veuillez nous excuser pour la gêne occasionnée."},
                status=status.HTTP_200_OK,
            )

        response_serializer = ChatResponseSerializer(data=result)
        response_serializer.is_valid(raise_exception=True)
        return Response(response_serializer.validated_data, status=status.HTTP_200_OK)


# ============================================================
#  AI SEARCH VIEW
# ============================================================

class AISearchView(APIView):
    """
    POST /api/v1/chatbot/search/

    Recherche intelligente multi-tables avec contrôle d'accès basé sur le rôle (RBAC).

    Règles d'accès :
      - Anonyme       : Produits, catégories, promotions uniquement.
      - customer      : Tout public + commandes, wallet, fidélité, livraisons, paiements.
      - platform_admin: Toutes les tables (données globales de la plateforme).

    Corps de la requête (JSON) :
      {
        "query": "mes dernières commandes livrées",
        "conversation_id": "uuid"
      }

    Réponse (JSON) :
      {
        "message": "Voici vos 3 dernières commandes... 🛍️",
        "results_count": 3,
        "role": "customer"
      }
    """

    authentication_classes = [TokenAuthentication, SessionAuthentication]
    permission_classes = [AllowAny]

    @extend_schema(
        summary="Chatbot IA — Recherche intelligente",
        description=(
            "Effectue une recherche contextuelle sur les données de la plateforme. "
            "Les données accessibles dépendent du rôle de l'utilisateur. "
            "La réponse est formatée en langage naturel par l'IA."
        ),
        request=AISearchRequestSerializer,
        responses={
            200: AISearchResponseSerializer,
            400: OpenApiResponse(description="Requête invalide."),
        },
        tags=["Chatbot IA"],
    )
    def post(self, request: Request) -> Response:
        serializer = AISearchRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        query: str = serializer.validated_data["query"]
        user = request.user if request.user.is_authenticated else None

        logger.info(
            "AISearchView: query=%r user=%s",
            query,
            user.email if user else "anonyme",
        )

        try:
            service = AISearchService(user=user, query=query)
            result = service.search()
        except Exception as exc:
            logger.error("AISearchView: erreur inattendue — %s", str(exc))
            return Response(
                {
                    "message": "La recherche IA est momentanément indisponible. Veuillez réessayer.",
                    "results_count": 0,
                    "role": "anonymous",
                },
                status=status.HTTP_200_OK,
            )

        return Response(result, status=status.HTTP_200_OK)


# ============================================================
#  RECOMMENDATIONS VIEW
# ============================================================

class RecommendationView(APIView):
    """
    POST /api/v1/chatbot/recommendations/

    Génère des recommandations de produits personnalisées.

    Stratégie :
      - Utilisateur avec commandes : Produits de la catégorie la plus commandée.
      - Utilisateur sans commandes / anonyme : Top produits par score composite
        (order_count × 0.5 + count_favorites × 0.3 + note_produit × 20 × 0.2).

    Corps de la requête (JSON) :
      {
        "products": [...],
        "cart_items": [...],
        "viewed_categories": [...],
        "user_intent": "...",
        "conversation_id": "uuid"
      }

    Réponse (JSON) :
      {
        "suggestions": [
          { "product_id": "uuid", "reason": "Basé sur vos achats...", "score": 4.2 },
          ...
        ],
        "conversation_id": null
      }
    """

    authentication_classes = [TokenAuthentication, SessionAuthentication]
    permission_classes = [AllowAny]

    @extend_schema(
        summary="Chatbot IA — Recommandations personnalisées",
        description=(
            "Retourne des recommandations de produits personnalisées basées sur "
            "l'historique d'achat de l'utilisateur, ou sur la popularité globale "
            "pour les utilisateurs anonymes ou sans historique."
        ),
        request=RecommendationRequestSerializer,
        responses={
            200: RecommendationResponseSerializer,
            400: OpenApiResponse(description="Requête invalide."),
        },
        tags=["Chatbot IA"],
    )
    def post(self, request: Request) -> Response:
        serializer = RecommendationRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        products_payload = serializer.validated_data.get("products", [])
        viewed_categories = serializer.validated_data.get("viewed_categories", [])
        user_intent = serializer.validated_data.get("user_intent", "")
        user = request.user if request.user.is_authenticated else None

        logger.info(
            "RecommendationView: user=%s products_in_payload=%d viewed_categories=%d",
            user.email if user else "anonyme",
            len(products_payload),
            len(viewed_categories),
        )

        try:
            service = RecommendationService(
                user=user,
                products_payload=products_payload,
                viewed_categories=viewed_categories,
                user_intent=user_intent,
            )
            suggestions = service.get_recommendations()
        except Exception as exc:
            logger.error("RecommendationView: erreur — %s", str(exc))
            return Response(
                {"suggestions": [], "conversation_id": None},
                status=status.HTTP_200_OK,
            )

        return Response(
            {
                "suggestions": suggestions,
                "conversation_id": serializer.validated_data.get("conversation_id"),
            },
            status=status.HTTP_200_OK,
        )
