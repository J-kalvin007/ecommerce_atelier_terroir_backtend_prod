"""
Signaux pour le module recettes.

Gère le nettoyage du stockage média (vidéo + images) : suppression des
fichiers physiques quand une recette est supprimée, et suppression de
l'ancien fichier quand il est remplacé par un nouveau (upload de
remplacement), afin d'éviter l'accumulation de fichiers orphelins sur le
storage (S3 en production, disque local en développement).
"""
import logging

from django.db.models.signals import post_delete, pre_save
from django.dispatch import receiver

from .models import Recette

logger = logging.getLogger(__name__)

# Champs de fichier dont le cycle de vie doit être aligné sur celui de la recette.
_MEDIA_FIELDS = ("video", "image_1", "image_2")


@receiver(post_delete, sender=Recette)
def delete_recette_media_files(sender, instance, **kwargs):
    """Supprime du storage les fichiers (vidéo, images) d'une recette supprimée."""
    for field_name in _MEDIA_FIELDS:
        field_file = getattr(instance, field_name)
        if field_file:
            field_file.storage.delete(field_file.name)


@receiver(pre_save, sender=Recette)
def delete_previous_recette_media_on_change(sender, instance, **kwargs):
    """
    Supprime l'ancien fichier physique quand un champ média est remplacé.

    Compare l'état stocké en base à l'instance en cours de sauvegarde ; si
    un champ média a changé (nouveau fichier ou suppression), l'ancien
    fichier est effacé du storage pour ne pas laisser de fichier orphelin.
    Ne fait rien à la création (aucune ligne existante en base à comparer).
    """
    try:
        previous = sender.objects.get(pk=instance.pk)
    except sender.DoesNotExist:
        return

    for field_name in _MEDIA_FIELDS:
        previous_file = getattr(previous, field_name)
        new_file = getattr(instance, field_name)

        if previous_file and previous_file.name != getattr(new_file, "name", None):
            previous_file.storage.delete(previous_file.name)
            logger.info(
                "Ancien fichier '%s' de la recette %s supprimé (remplacé).",
                field_name,
                instance.pk,
            )
