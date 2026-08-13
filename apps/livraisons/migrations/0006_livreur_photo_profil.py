# Migration manuelle — Ajout du champ photo_profil au modèle Livreur
# Dépend de: 0005_rename_livraisons__deliver_404419_idx_livraisons__deliver_d4bb63_idx_and_more

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        (
            "livraisons",
            "0005_rename_livraisons__deliver_404419_idx_livraisons__deliver_d4bb63_idx_and_more",
        ),
    ]

    operations = [
        migrations.AddField(
            model_name="livreur",
            name="photo_profil",
            field=models.ImageField(
                blank=True,
                help_text="Photo de profil du livreur (optionnel, formats: JPG, PNG, WEBP).",
                null=True,
                upload_to="livreurs/photos/",
                verbose_name="Photo de profil",
            ),
        ),
    ]
