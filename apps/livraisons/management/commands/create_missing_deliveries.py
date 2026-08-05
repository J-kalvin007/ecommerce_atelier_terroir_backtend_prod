"""
Management command : create_missing_deliveries
==============================================

Crée les livraisons manquantes pour toutes les commandes payées (status='paid')
qui sont marquées pour livraison (is_for_delivery=True) et qui n'ont pas encore
d'entrée dans la table livraisons_delivery.

Usage :
    python manage.py create_missing_deliveries
    python manage.py create_missing_deliveries --dry-run        # simulation sans écriture
    python manage.py create_missing_deliveries --order-id <uuid> # pour une commande spécifique
"""

from django.core.management.base import BaseCommand
from django.db import transaction


class Command(BaseCommand):
    help = "Crée les livraisons manquantes pour toutes les commandes payées marquées pour livraison."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Simule la commande sans créer de livraisons en base.",
        )
        parser.add_argument(
            "--order-id",
            type=str,
            default=None,
            help="Traite uniquement la commande avec cet ID (UUID).",
        )

    def handle(self, *args, **options):
        from apps.commandes.models import Order, OrderStatus
        from apps.livraisons.models import Delivery, DeliveryStatus

        dry_run = options["dry_run"]
        order_id = options.get("order_id")

        # Construire le queryset des commandes éligibles
        qs = Order.objects.filter(
            status=OrderStatus.PAID,
            is_for_delivery=True,
        ).exclude(
            delivery__isnull=False  # exclure celles qui ont déjà une livraison
        ).select_related("user")

        if order_id:
            qs = qs.filter(pk=order_id)

        total = qs.count()

        if total == 0:
            self.stdout.write(self.style.SUCCESS(
                "✅ Aucune livraison manquante détectée. Tout est à jour."
            ))
            return

        self.stdout.write(self.style.WARNING(
            f"🔍 {total} commande(s) payée(s) sans livraison détectée(s)."
        ))

        if dry_run:
            self.stdout.write(self.style.NOTICE("⚠️  Mode dry-run activé — aucune écriture en base."))

        created_count = 0
        error_count = 0

        for order in qs:
            try:
                if dry_run:
                    self.stdout.write(
                        f"  [DRY-RUN] Commande {order.numero_commande or order.pk} → "
                        f"livraison serait créée à l'adresse : {order.address_livraison!r}"
                    )
                    created_count += 1
                else:
                    with transaction.atomic():
                        delivery, created = Delivery.objects.get_or_create(
                            order=order,
                            defaults={
                                "status": DeliveryStatus.PENDING,
                                "delivery_address": order.address_livraison or "",
                                "notes": order.notes or "",
                                "created_by": order.user,
                            },
                        )
                    if created:
                        created_count += 1
                        self.stdout.write(self.style.SUCCESS(
                            f"  ✅ Livraison créée pour la commande {order.numero_commande or order.pk}"
                        ))
                    else:
                        self.stdout.write(self.style.NOTICE(
                            f"  ⚠️  Livraison déjà existante pour la commande {order.numero_commande or order.pk} (ignorée)"
                        ))
            except Exception as exc:
                error_count += 1
                self.stdout.write(self.style.ERROR(
                    f"  ❌ Erreur pour la commande {order.numero_commande or order.pk} : {exc}"
                ))

        # Résumé
        verb = "auraient été créées" if dry_run else "créées"
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(
            f"✅ Terminé — {created_count} livraison(s) {verb}, {error_count} erreur(s)."
        ))
