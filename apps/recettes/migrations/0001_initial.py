# Generated manually

import uuid

import apps.recettes.models
import django.core.validators
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("catalog", "0006_alter_productvariant_product"),
        ("promotions", "0007_pack_recette"),
    ]

    operations = [
        migrations.CreateModel(
            name="Recette",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("is_active", models.BooleanField(db_index=True, default=True)),
                ("nom", models.CharField(blank=True, max_length=255, null=True, verbose_name="Nom de la recette")),
                ("description", models.TextField(blank=True, help_text="Court résumé éditorial de la recette.", null=True, verbose_name="Description")),
                ("ingredients", models.TextField(blank=True, help_text="Liste des ingrédients de la recette (un par ligne).", null=True, verbose_name="Ingrédients")),
                ("instructions", models.TextField(blank=True, help_text="Étapes de préparation de la recette.", null=True, verbose_name="Instructions")),
                ("video_url", models.URLField(blank=True, help_text="Lien vers une vidéo externe (YouTube, Vimeo, etc.).", max_length=500, null=True, verbose_name="Lien vidéo externe")),
                (
                    "video",
                    models.FileField(
                        blank=True,
                        help_text="Vidéo de la recette uploadée directement. Compressée automatiquement côté serveur pour ne jamais dépasser 10 Mo.",
                        null=True,
                        upload_to="recettes/videos/%Y/%m/",
                        validators=[
                            django.core.validators.FileExtensionValidator(allowed_extensions=["mp4", "mov", "avi", "mkv", "webm", "m4v"]),
                            apps.recettes.models.validate_recette_video_upload_size,
                        ],
                        verbose_name="Vidéo hébergée",
                    ),
                ),
                ("image_1", models.ImageField(blank=True, null=True, upload_to="recettes/images/%Y/%m/", verbose_name="Image 1")),
                ("image_2", models.ImageField(blank=True, null=True, upload_to="recettes/images/%Y/%m/", verbose_name="Image 2")),
                (
                    "pack",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="recettes",
                        to="promotions.pack",
                        verbose_name="Pack associé",
                    ),
                ),
                (
                    "product",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="recettes",
                        to="catalog.product",
                        verbose_name="Produit associé",
                    ),
                ),
            ],
            options={
                "verbose_name": "Recette",
                "verbose_name_plural": "Recettes",
                "db_table": "recettes_recettes",
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddConstraint(
            model_name="recette",
            constraint=models.CheckConstraint(
                check=~(models.Q(product__isnull=False) & models.Q(pack__isnull=False)),
                name="recette_produit_xor_pack",
                violation_error_message="Une recette ne peut être liée qu'à un seul produit OU un seul pack, jamais les deux à la fois.",
            ),
        ),
    ]
