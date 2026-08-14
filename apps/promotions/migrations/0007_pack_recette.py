# Generated manually for Render deployment

from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('promotions', '0006_alter_pack_description_alter_pack_name_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='pack',
            name='recette',
            field=models.TextField(blank=True, help_text='Liste des recettes ou plats possibles à faire facilement avec ce pack de produits.', null=True, verbose_name='Recette(s) conseillée(s)'),
        ),
    ]
