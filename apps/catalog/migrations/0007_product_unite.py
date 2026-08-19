# Generated manually for Django

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('catalog', '0006_alter_productvariant_product'),
    ]

    operations = [
        migrations.AddField(
            model_name='product',
            name='unite',
            field=models.CharField(blank=True, max_length=20, null=True),
        ),
    ]
