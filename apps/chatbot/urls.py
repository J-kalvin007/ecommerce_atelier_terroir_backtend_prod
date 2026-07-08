"""
URLs du module Chatbot IA.

Endpoints :
  POST /api/v1/chatbot/chat/           — Conversation IA
  POST /api/v1/chatbot/search/         — Recherche intelligente multi-tables (RBAC)
  POST /api/v1/chatbot/recommendations/ — Recommandations personnalisées

Ce fichier est inclus dans config/urls.py avec le préfixe "api/v1/chatbot/".

@module apps.chatbot.urls
"""
from django.urls import path

from .views import ChatView, AISearchView, RecommendationView

app_name = "chatbot"

urlpatterns = [
    path(
        "chat/",
        ChatView.as_view(),
        name="chat",
    ),
    path(
        "search/",
        AISearchView.as_view(),
        name="ai-search",
    ),
    path(
        "recommendations/",
        RecommendationView.as_view(),
        name="recommendations",
    ),
]
