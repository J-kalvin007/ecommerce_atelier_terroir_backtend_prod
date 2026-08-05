# Generated manually

from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('commandes', '0009_cartpackitem'),
        ('promotions', '0004_pack_packitem'),
    ]

    operations = [
        migrations.CreateModel(
            name='OrderPack',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('is_active', models.BooleanField(db_index=True, default=True)),
                ('pack_name', models.CharField(max_length=255)),
                ('quantity', models.PositiveIntegerField()),
                ('unit_price', models.DecimalField(decimal_places=2, max_digits=12)),
                ('subtotal', models.DecimalField(decimal_places=2, max_digits=12)),
                ('order', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='packs', to='commandes.order')),
                ('pack', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='promotions.pack')),
            ],
            options={
                'verbose_name': 'Pack commandé',
                'verbose_name_plural': 'Packs commandés',
                'db_table': 'commandes_order_packs',
            },
        ),
        migrations.AddIndex(
            model_name='orderpack',
            index=models.Index(fields=['order'], name='commandes_o_order_i_626871_idx'),
        ),
        migrations.AddField(
            model_name='orderitem',
            name='order_pack',
            field=models.ForeignKey(blank=True, help_text="Si cet article fait partie d'un pack commandé.", null=True, on_delete=django.db.models.deletion.CASCADE, related_name='items', to='commandes.orderpack'),
        ),
    ]
