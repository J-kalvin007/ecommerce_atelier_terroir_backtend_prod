# Generated manually

from django.db import migrations, models
import django.db.models.deletion
import uuid
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('livraisons', '0003_add_livreur'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='delivery',
            name='livreur',
            field=models.ForeignKey(blank=True, help_text='Le profil livreur assigné à cette livraison.', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='deliveries', to='livraisons.livreur', verbose_name='Livreur assigné'),
        ),
        migrations.AlterField(
            model_name='delivery',
            name='status',
            field=models.CharField(choices=[('pending', 'En attente'), ('assigned', 'Assignée'), ('in_transit', 'En transit'), ('delivered', 'Livrée'), ('cancelled', 'Annulée')], db_index=True, default='pending', max_length=20),
        ),
        migrations.CreateModel(
            name='DeliveryStatusHistory',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('is_active', models.BooleanField(db_index=True, default=True)),
                ('old_status', models.CharField(blank=True, choices=[('pending', 'En attente'), ('assigned', 'Assignée'), ('in_transit', 'En transit'), ('delivered', 'Livrée'), ('cancelled', 'Annulée')], max_length=20, null=True, verbose_name='Ancien statut')),
                ('new_status', models.CharField(choices=[('pending', 'En attente'), ('assigned', 'Assignée'), ('in_transit', 'En transit'), ('delivered', 'Livrée'), ('cancelled', 'Annulée')], max_length=20, verbose_name='Nouveau statut')),
                ('notes', models.TextField(blank=True, verbose_name='Notes / Motif')),
                ('changed_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL, verbose_name='Modifié par')),
                ('delivery', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='status_history', to='livraisons.delivery', verbose_name='Livraison')),
            ],
            options={
                'verbose_name': 'Historique de livraison',
                'verbose_name_plural': 'Historiques de livraison',
                'db_table': 'livraisons_delivery_history',
                'ordering': ['-created_at'],
                'indexes': [models.Index(fields=['delivery', '-created_at'], name='livraisons__deliver_404419_idx')],
            },
        ),
    ]
