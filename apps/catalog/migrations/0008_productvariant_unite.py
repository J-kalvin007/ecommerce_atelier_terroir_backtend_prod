# Generated manually for Django

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('catalog', '0007_product_unite'),
    ]

    operations = [
        migrations.AddField(
            model_name='productvariant',
            name='unite',
            field=models.CharField(blank=True, max_length=20, null=True),
        ),
    ]
