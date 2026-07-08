"""
Vues DRF du module Chatbot IA.

Endpoint unique :
  POST /api/v1/chatbot/chat/

La vue délègue entièrement la logique métier à ChatService.
Elle se contente de :
  1. Valider la requête entrante via ChatRequestSerializer.
  2. Identifier l'utilisateur (authentifié ou anonyme).
  3. Instancier ChatService et appeler process_message().
  4. Retourner la réponse sérialisée.

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

from .serializers import ChatRequestSerializer, ChatResponseSerializer
from .services import ChatService

logger = logging.getLogger(__name__)


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
        "message": "Quels produits bio avez-vous ?",          // obligatoire
        "conversation_id": "uuid-de-la-conversation"          // optionnel
      }

    Réponse (JSON) :
      {
        "message": "Nous avons les produits suivants...",
        "conversation_id": "uuid-de-la-conversation"
      }

    Codes d'erreur :
      400 : Message manquant ou invalide.
      503 : Service OpenAI temporairement indisponible.
    """

    # Authentification optionnelle : TokenAuthentication est tentée,
    # mais si le token est absent, l'utilisateur reste anonyme (None).
    authentication_classes = [TokenAuthentication, SessionAuthentication]

    # AllowAny : même un utilisateur non authentifié peut accéder à l'endpoint.
    # La restriction des fonctionnalités privées est gérée dans ChatService.
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
        """
        Traite un message envoyé au chatbot IA.

        Args:
            request: Requête HTTP avec les champs 'message' et 'conversation_id'.

        Returns:
            Response avec 'message' (réponse IA) et 'conversation_id'.
        """
        # --- 1. Validation de la requête entrante ---
        serializer = ChatRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        user_message: str = serializer.validated_data["message"]
        conversation_id = serializer.validated_data.get("conversation_id")

        # --- 2. Identification de l'utilisateur ---
        # request.user est soit un utilisateur authentifié, soit AnonymousUser.
        # ChatService reçoit None pour les anonymes.
        user = request.user if request.user.is_authenticated else None

        # --- 3. Délégation au service IA ---
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
            
            return Response(
                {"message": error_message},
                status=status.HTTP_200_OK,
            )
        except openai.OpenAIError as exc:
            logger.error("ChatView: erreur OpenAI inattendue — %s", str(exc))
            return Response(
                {"message": "Le chatbot IA est momentanément indisponible suite à une erreur technique. Veuillez nous excuser pour la gêne occasionnée."},
                status=status.HTTP_200_OK,
            )

        # --- 4. Sérialisation et retour de la réponse ---
        response_serializer = ChatResponseSerializer(data=result)
        response_serializer.is_valid(raise_exception=True)

        return Response(response_serializer.validated_data, status=status.HTTP_200_OK)
