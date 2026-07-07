


"""
Signaux pour la mise à jour automatique du compteur dénormalisé de favoris
sur le modèle Product.

Utilise TOUJOURS un Count() sur la table Favorite pour éviter toute
incohérence liée à un incrément/décrément manuel (+1/-1).
"""
import logging
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from apps.catalog.models import Product
from .models import Favorite
from django.db.models import Avg, Count
from .models import Rating


logger = logging.getLogger(__name__)





def _recalculate_product_favorite_count(product: Product) -> None:
    """
    Recalcule le compteur de favoris d'un produit en comptant les entrées
    dans la table Favorite.
    
    Utilise update_fields pour éviter de déclencher d'autres signaux
    sur le modèle Product (cascades infinies).
    
    Args:
        product: L'instance Product dont le compteur doit être mis à jour.
    """
    count = Favorite.objects.filter(product=product).count()
    product.count_favorites = count
    product.save(update_fields=["count_favorites", "updated_at"])
    logger.debug(
        "Product %s count_favorites updated to %d",
        product.sku,
        count,
    )


@receiver(post_save, sender=Favorite)
def update_favorite_count_on_save(sender, instance, created, **kwargs):
    """
    Recalcule count_favorites après chaque création de Favorite.
    
    Note: update_or_create ne déclenchera ce signal que pour les créations
    (created=True), pas pour les mises à jour (un Favorite n'a pas de champs
    modifiables à part created_at).
    """
    if created:
        _recalculate_product_favorite_count(instance.product)


@receiver(post_delete, sender=Favorite)
def update_favorite_count_on_delete(sender, instance, **kwargs):
    """Recalcule count_favorites après chaque suppression de Favorite."""
    _recalculate_product_favorite_count(instance.product)














"""
Signaux pour la mise à jour automatique des agrégats dénormalisés de notation
sur le modèle Product : note_produit (moyenne) et count_ratings (nombre).

Utilise TOUJOURS une requête d'agrégation (Avg + Count) pour éviter
les incohérences de calcul manuel (+1/-1 sur la moyenne).
"""



def _recalculate_product_rating(product: Product) -> None:
    """
    Recalcule la note moyenne et le nombre total de notes d'un produit
    en exécutant une requête d'agrégation sur la table Rating.
    
    Args:
        product: L'instance Product à mettre à jour.
    """
    aggregates = Rating.objects.filter(product=product).aggregate(
        avg_score=Avg("score"),
        count_ratings=Count("id"),
    )
    # Avg() retourne None s'il n'y a pas de notes, on utilise 0.00 par défaut
    product.note_produit = round(aggregates["avg_score"] or 0.0, 2)
    product.count_ratings = aggregates["count_ratings"] or 0
    product.save(update_fields=["note_produit", "count_ratings", "updated_at"])
    logger.debug(
        "Product %s rating updated: avg=%.2f, count=%d",
        product.sku,
        product.note_produit,
        product.count_ratings,
    )


@receiver(post_save, sender=Rating)
def update_rating_on_save(sender, instance, created, **kwargs):
    """
    Recalcule les agrégats de notation après chaque création ou modification
    de note.
    
    Note: le signal est déclenché pour created=True ET pour les mises à jour
    (update_or_create), ce qui garantit que la moyenne est toujours juste.
    """
    _recalculate_product_rating(instance.product)


@receiver(post_delete, sender=Rating)
def update_rating_on_delete(sender, instance, **kwargs):
    """Recalcule les agrégats après la suppression d'une note."""
    _recalculate_product_rating(instance.product)


@receiver(post_save, sender=Product)
def sync_default_variant_for_product(sender, instance, created, **kwargs):
    """
    Crée automatiquement une variante par défaut contenant les mêmes données
    que le produit principal lors de sa création.
    Maintient également le stock de la variante par défaut synchronisé avec le produit.
    """
    from apps.catalog.models import ProductVariant
    from django.utils import timezone
    
    stock_value = instance.stock if instance.stock is not None else 0

    if created:
        ProductVariant.objects.create(
            product=instance,
            name=instance.name[:100],  # limité à 100 char max comme défini dans le modèle
            sku=instance.sku,
            price=instance.price,
            stock=stock_value,
            weight_grams=instance.weight_grams,
        )
        logger.info(f"Variante par défaut créée pour le produit {instance.sku}")
    else:
        # Met à jour le stock de la variante par défaut (la plus ancienne)
        default_variant = ProductVariant.objects.filter(product=instance).order_by('created_at').first()
        if default_variant and default_variant.stock != stock_value:
            ProductVariant.objects.filter(id=default_variant.id).update(
                stock=stock_value,
                updated_at=timezone.now()
            )
            logger.info(f"Stock de la variante par défaut mis à jour pour le produit {instance.sku}")

from apps.catalog.models import ProductVariant

@receiver(post_save, sender=ProductVariant)
def sync_product_stock_from_default_variant(sender, instance, created, **kwargs):
    """
    Maintient le stock du produit principal synchronisé si le stock de sa 
    variante par défaut est modifié.
    """
    from apps.catalog.models import Product
    from django.utils import timezone

    stock_value = instance.stock if instance.stock is not None else 0
    if instance.stock is None:
        sender.objects.filter(id=instance.id).update(stock=0, updated_at=timezone.now())

    default_variant = sender.objects.filter(product_id=instance.product_id).order_by('created_at').first()
    if default_variant and default_variant.id == instance.id:
        product = instance.product
        if product.stock != stock_value:
            Product.objects.filter(id=product.id).update(
                stock=stock_value,
                updated_at=timezone.now()
            )
            logger.info(f"Stock du produit {product.sku} synchronisé depuis sa variante par défaut")