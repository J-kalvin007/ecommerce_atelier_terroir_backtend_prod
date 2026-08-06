# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('promotions', '0004_pack_packitem'),
    ]

    operations = [
        migrations.AddField(
            model_name='pack',
            name='slug',
            field=models.SlugField(blank=True, help_text='Identifiant URL du pack. Auto-généré depuis le nom si laissé vide.', max_length=120, null=True, unique=True, verbose_name='Slug'),
        ),
    ]
