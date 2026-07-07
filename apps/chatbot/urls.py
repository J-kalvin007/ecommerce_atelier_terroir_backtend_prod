"""
URLs du module Chatbot IA.

Endpoint unique :
  POST /api/v1/chatbot/chat/

Ce fichier est inclus dans config/urls.py avec le préfixe "api/v1/chatbot/".

@module apps.chatbot.urls
"""
from django.urls import path

from .views import ChatView

app_name = "chatbot"

urlpatterns = [
    path(
        "chat/",
        ChatView.as_view(),
        name="chat",
    ),
]
