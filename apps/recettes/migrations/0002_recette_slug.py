# Generated manually for Django

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('recettes', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='recette',
            name='slug',
            field=models.SlugField(blank=True, db_index=True, max_length=255, null=True, unique=True, verbose_name='Slug'),
        ),
    ]
