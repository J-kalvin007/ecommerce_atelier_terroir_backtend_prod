"""
Commande de management : expiration des points de fidélité.

Raison d'être
-------------
`apps.fidelites.tasks.expire_points_task` n'a jamais pu s'exécuter en
production : Celery y tourne en mode EAGER avec un broker `memory://`, et aucun
service worker/beat n'est déployé (un seul service web sur Render). Résultat
vérifié : les points gagnés à l'achat sont bien attribués — en synchrone, via
signal — mais rien n'expire jamais.

Cette commande expose la même logique métier (`LoyaltyService.expire_points`)
sous une forme directement branchable sur un cron Render, sans exiger de
broker ni de worker :

    python manage.py expirer_points_fidelite

Le jour où un vrai worker Celery est déployé, la tâche planifiée
`loyalty.expire_points` reprend le relais : les deux points d'entrée appellent
strictement le même service, il n'y a aucune logique dupliquée.

@module apps.fidelites.management.commands.expirer_points_fidelite
"""

import logging

from django.core.management.base import BaseCommand, CommandError

from apps.fidelites.services import LoyaltyService

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        "Expire les points de fidélité dont la date d'expiration est dépassée. "
        "À planifier quotidiennement (cron Render, ex. 02:00 UTC)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help=(
                "Affiche le nombre d'événements qui seraient expirés sans "
                "modifier aucun solde."
            ),
        )

    def handle(self, *args, **options):
        if options["dry_run"]:
            count = self._count_expirable_events()
            self.stdout.write(
                self.style.WARNING(
                    f"[dry-run] {count} événement(s) de points seraient expirés.",
                ),
            )
            return

        self.stdout.write("Démarrage de l'expiration des points de fidélité...")
        try:
            processed = LoyaltyService.expire_points()
        except Exception as exc:  # noqa: BLE001 - remonté en CommandError explicite
            logger.exception("Échec de l'expiration des points de fidélité.")
            msg = f"Expiration des points interrompue : {exc}"
            raise CommandError(msg) from exc

        self.stdout.write(
            self.style.SUCCESS(
                f"Expiration terminée : {processed} événement(s) traité(s).",
            ),
        )

    @staticmethod
    def _count_expirable_events() -> int:
        """Compte, sans rien modifier, les événements de points expirés."""
        from django.utils import timezone

        from apps.fidelites.models import LoyaltyEvent

        return LoyaltyEvent.objects.filter(
            reason=LoyaltyEvent.Reason.PURCHASE,
            points_delta__gt=0,
            expires_at__isnull=False,
            expires_at__lt=timezone.now(),
        ).count()
