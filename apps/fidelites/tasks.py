


"""
Tâches planifiées Celery pour le module de fidélisation.

- expire_points : quotidienne, expire les points dépassés

Nom enregistré de la tâche : ``loyalty.expire_points`` — c'est cette chaîne, et
non le chemin d'import, que doit référencer CELERY_BEAT_SCHEDULE.

Tant qu'aucun worker Celery n'est déployé (Celery tourne en mode EAGER en
production), l'expiration doit être déclenchée par la commande de management
``python manage.py expirer_points_fidelite``, branchée sur un cron Render.
Les deux points d'entrée appellent le même service : aucune logique dupliquée.

Aucune tâche ``birthday_bonus_task`` n'est définie : le modèle User ne porte
pas de date de naissance. L'entrée correspondante a été retirée de
CELERY_BEAT_SCHEDULE, où elle référençait une tâche inexistante.
"""
from celery import shared_task
from celery.utils.log import get_task_logger

from .services import LoyaltyService

logger = get_task_logger(__name__)


@shared_task(name="loyalty.expire_points")
def expire_points_task():
    """
    Tâche planifiée : expire les points de fidélité dont la date est dépassée.

    Planification recommandée : quotidienne, ex. 02:00 UTC.
    """
    logger.info("Démarrage de la tâche d'expiration des points...")
    try:
        processed = LoyaltyService.expire_points()
        logger.info(f"Expiration terminée : {processed} événements traités.")
        return processed
    except Exception as e:
        logger.error(f"Erreur lors de l'expiration des points : {e}")
        raise

