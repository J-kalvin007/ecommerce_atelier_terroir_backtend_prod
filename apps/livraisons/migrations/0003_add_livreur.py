# Generated manually

import uuid
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('livraisons', '0002_fraislivraison_coordonnee_admin'),
    ]

    operations = [
        migrations.CreateModel(
            name='Livreur',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('is_active', models.BooleanField(db_index=True, default=True)),
                ('nom', models.CharField(help_text='Nom de famille du livreur.', max_length=100, verbose_name='Nom')),
                ('prenom', models.CharField(help_text='Prénom du livreur.', max_length=100, verbose_name='Prénom')),
                ('telephone', models.CharField(db_index=True, help_text='Numéro de téléphone principal du livreur.', max_length=30, verbose_name='Téléphone')),
                ('email', models.EmailField(blank=True, help_text='Adresse email du livreur (optionnel).', max_length=254, null=True, verbose_name='Email')),
                ('type_vehicule', models.CharField(choices=[('moto', 'Moto'), ('tricycle', 'Tricycle'), ('voiture', 'Voiture'), ('camionnette', 'Camionnette'), ('velo', 'Vélo'), ('a_pied', 'À pied')], help_text='Type de véhicule utilisé pour les livraisons.', max_length=20, verbose_name='Type de véhicule')),
                ('zone_livraison', models.CharField(blank=True, help_text='Zone géographique couverte par le livreur (texte libre).', max_length=255, verbose_name='Zone de livraison')),
                ('notes', models.TextField(blank=True, help_text='Informations internes sur le livreur (non visibles du client).', verbose_name='Notes internes')),
                ('user', models.OneToOneField(blank=True, help_text='Compte plateforme associé à ce livreur (optionnel).', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='profil_livreur', to=settings.AUTH_USER_MODEL, verbose_name='Compte utilisateur')),
            ],
            options={
                'verbose_name': 'Livreur',
                'verbose_name_plural': 'Livreurs',
                'db_table': 'livraisons_livreurs',
                'ordering': ['nom', 'prenom'],
                'indexes': [
                    models.Index(fields=['telephone'], name='livraisons_livreur_tel_idx'),
                    models.Index(fields=['is_active'], name='livraisons_livreur_active_idx'),
                ],
            },
        ),
    ]
