# Generated manually — 2026-07-21
# Adds numero_commande, nom_client, prenom_client, email_client to Order
# and makes the user FK nullable to support anonymous checkouts.

import django.db.models.deletion
import django.conf
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('commandes', '0006_alter_cartitem_product'),
        migrations.swappable_dependency(django.conf.settings.AUTH_USER_MODEL),
    ]

    operations = [
        # 1. Make Order.user nullable (anonymous checkout support)
        migrations.AlterField(
            model_name='order',
            name='user',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='orders',
                to=django.conf.settings.AUTH_USER_MODEL,
            ),
        ),

        # 2. Add numero_commande (auto-generated friendly order number)
        migrations.AddField(
            model_name='order',
            name='numero_commande',
            field=models.CharField(
                blank=True,
                max_length=100,
                null=True,
                unique=True,
            ),
        ),

        # 3. Add nom_client (guest / override client last name)
        migrations.AddField(
            model_name='order',
            name='nom_client',
            field=models.CharField(
                blank=True,
                max_length=100,
                null=True,
            ),
        ),

        # 4. Add prenom_client (guest / override client first name)
        migrations.AddField(
            model_name='order',
            name='prenom_client',
            field=models.CharField(
                blank=True,
                max_length=100,
                null=True,
            ),
        ),

        # 5. Add email_client (guest / override client email for invoice)
        migrations.AddField(
            model_name='order',
            name='email_client',
            field=models.EmailField(
                blank=True,
                null=True,
            ),
        ),
    ]
