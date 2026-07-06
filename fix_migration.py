import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.local')
django.setup()

from django.db import connection

with connection.cursor() as cursor:
    # On insère une variante par défaut pour TOUS les produits existants, 
    # en utilisant le MEME UUID (id) que le produit. Ainsi, les OrderItems et CartItems
    # qui pointent déjà vers l'ID du produit pointeront validement vers l'ID de la variante !
    cursor.execute("""
        INSERT INTO catalog_productvariant (id, created_at, updated_at, product_id, name, sku, price, stock, weight_grams, is_active)
        SELECT id, created_at, updated_at, id, substring(name from 1 for 100), sku, price, stock, weight_grams, is_active
        FROM catalog_product
        ON CONFLICT (id) DO NOTHING;
    """)

print("✅ Variantes de base créées pour tous les produits existants. La contrainte de clé étrangère sera respectée.")
