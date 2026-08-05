# Generated manually

from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('commandes', '0008_order_is_for_delivery'),
        ('promotions', '0004_pack_packitem'),
    ]

    operations = [
        migrations.CreateModel(
            name='CartPackItem',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('is_active', models.BooleanField(db_index=True, default=True)),
                ('quantity', models.PositiveIntegerField(default=1)),
                ('cart', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='pack_items', to='commandes.cart')),
                ('pack', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='cart_items', to='promotions.pack')),
            ],
            options={
                'verbose_name': 'Pack de panier',
                'verbose_name_plural': 'Packs de panier',
                'db_table': 'commandes_cart_pack_items',
            },
        ),
        migrations.AddConstraint(
            model_name='cartpackitem',
            constraint=models.UniqueConstraint(fields=('cart', 'pack'), name='unique_cartpackitem_cart_pack'),
        ),
    ]
