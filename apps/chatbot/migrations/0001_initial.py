# Generated manually - 2026-07-08
import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Conversation",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True, db_index=True),
                ),
                (
                    "updated_at",
                    models.DateTimeField(auto_now=True),
                ),
                (
                    "is_active",
                    models.BooleanField(db_index=True, default=True),
                ),
                (
                    "user",
                    models.ForeignKey(
                        blank=True,
                        help_text="Null pour les visiteurs anonymes.",
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="chatbot_conversations",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Utilisateur",
                    ),
                ),
            ],
            options={
                "verbose_name": "Conversation",
                "verbose_name_plural": "Conversations",
                "db_table": "chatbot_conversations",
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="Message",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True, db_index=True),
                ),
                (
                    "updated_at",
                    models.DateTimeField(auto_now=True),
                ),
                (
                    "is_active",
                    models.BooleanField(db_index=True, default=True),
                ),
                (
                    "role",
                    models.CharField(
                        choices=[
                            ("user", "Utilisateur"),
                            ("assistant", "Assistant IA"),
                        ],
                        help_text="'user' pour les messages du client, 'assistant' pour les réponses IA.",
                        max_length=10,
                        verbose_name="Rôle",
                    ),
                ),
                (
                    "content",
                    models.TextField(
                        help_text="Texte brut du message.",
                        verbose_name="Contenu",
                    ),
                ),
                (
                    "conversation",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="messages",
                        to="chatbot.conversation",
                        verbose_name="Conversation",
                    ),
                ),
            ],
            options={
                "verbose_name": "Message",
                "verbose_name_plural": "Messages",
                "db_table": "chatbot_messages",
                "ordering": ["created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="conversation",
            index=models.Index(
                fields=["user", "-created_at"],
                name="chatbot_con_user_id_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="message",
            index=models.Index(
                fields=["conversation", "created_at"],
                name="chatbot_mes_convers_idx",
            ),
        ),
    ]
