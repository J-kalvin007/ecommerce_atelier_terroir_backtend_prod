# Generated manually

from django.db import migrations, models
import django.db.models.deletion
from decimal import Decimal
import django.core.validators
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('promotions', '0003_delete_promousage'),
        ('catalog', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Pack',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('is_active', models.BooleanField(db_index=True, default=True)),
                ('name', models.CharField(max_length=100, verbose_name='Nom du pack')),
                ('description', models.TextField(blank=True, verbose_name='Description')),
                ('price', models.DecimalField(decimal_places=2, help_text='Prix fixe global du pack (souvent inférieur à la somme des produits).', max_digits=12, validators=[django.core.validators.MinValueValidator(Decimal('0.01'))], verbose_name='Prix du pack')),
                ('image', models.ImageField(blank=True, null=True, upload_to='packs/', verbose_name='Image')),
            ],
            options={
                'verbose_name': 'Pack produit',
                'verbose_name_plural': 'Packs produits',
                'db_table': 'promotions_packs',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='PackItem',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('is_active', models.BooleanField(db_index=True, default=True)),
                ('quantity', models.PositiveIntegerField(default=1, validators=[django.core.validators.MinValueValidator(1)], verbose_name='Quantité')),
                ('pack', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='items', to='promotions.pack')),
                ('product_variant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='pack_inclusions', to='catalog.productvariant', verbose_name='Variante de produit')),
            ],
            options={
                'verbose_name': 'Article de pack',
                'verbose_name_plural': 'Articles de pack',
                'db_table': 'promotions_pack_items',
                'unique_together': {('pack', 'product_variant')},
            },
        ),
    ]
