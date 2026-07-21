# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('commandes', '0007_order_anonymous_and_client_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='is_for_delivery',
            field=models.BooleanField(default=True, help_text='Indique si la commande doit être livrée (True) ou retirée en boutique (False).'),
        ),
    ]
