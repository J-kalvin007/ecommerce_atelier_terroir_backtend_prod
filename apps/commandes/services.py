from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.commandes.models import Order, OrderItem, OrderPack, OrderStatusHistory, OrderStatus


class OrderService:

    @staticmethod
    def calculate_totals(items, products_cache, frais_livraison=Decimal("0.00"), discount_amount=Decimal("0.00")):
        """
        Calcule les montants de la commande sans refaire de requêtes DB.
        """
        items_total = Decimal("0.00")

        for item in items:
            product = products_cache[str(item["product_id"])]
            quantity = item["quantity"]
            items_total += product.price * quantity

        tax_amount = Decimal("0.00")
        total_final = items_total + tax_amount + frais_livraison - discount_amount

        return {
            "items_total": items_total,
            "tax_amount": tax_amount,
            "frais_livraison": frais_livraison,
            "discount_amount": discount_amount,
            "total_final": total_final,
        }

    @staticmethod
    @transaction.atomic
    def create_order(
        *,
        user,
        items=None,
        packs=None,
        address_livraison,
        phone_livraison,
        city,
        country,
        nom_client="",
        prenom_client="",
        email_client="",
        notes="",
        is_for_delivery=True,
        frais_livraison=Decimal("0.00"),
        discount_amount=Decimal("0.00"),
    ):
        """
        Création complète d'une commande incluant des produits simples et/ou des packs.
        """
        from apps.catalog.models import ProductVariant
        from apps.promotions.models import Pack
        from apps.promotions.services import PackService

        items = items or []
        packs = packs or []

        if not items and not packs:
            raise ValidationError(
                "La commande doit contenir au moins un produit ou un pack."
            )

        variants_cache = {}

        for item in items:
            pid = str(item["product_id"])

            # 1. Chercher d'abord dans ProductVariant directement
            variant = ProductVariant.objects.filter(
                id=pid,
                is_active=True,
            ).first()

            # 2. Fallback : si l'id correspond à un Product, prendre sa première variante active
            if not variant:
                variant = ProductVariant.objects.filter(
                    product_id=pid,
                    is_active=True,
                ).first()

            if not variant:
                raise ValidationError(
                    f"Variante introuvable pour l'identifiant {pid}."
                )

            quantity = item["quantity"]

            if quantity <= 0:
                raise ValidationError(
                    "La quantité doit être supérieure à zéro."
                )

            if variant.stock < quantity:
                raise ValidationError(
                    f"Stock insuffisant pour {variant.product.name} — {variant.name}"
                )

            variants_cache[pid] = variant

        packs_cache = {}
        for p in packs:
            pid = str(p["pack_id"])
            pack = Pack.objects.filter(id=pid, is_active=True).first()
            if not pack:
                raise ValidationError(f"Pack introuvable: {pid}")
                
            qty = p["quantity"]
            if qty <= 0:
                raise ValidationError("La quantité de pack doit être supérieure à zéro.")
                
            from apps.promotions.exceptions import PackError
            try:
                PackService.check_pack_availability(pack, qty)
            except PackError as e:
                raise ValidationError(str(e))
                
            packs_cache[pid] = pack

        # Calcul des totaux sur la base des prix des variantes et des packs
        items_total = Decimal("0.00")
        for item in items:
            v = variants_cache[str(item["product_id"])]
            items_total += v.price * item["quantity"]
            
        for p in packs:
            pack = packs_cache[str(p["pack_id"])]
            items_total += pack.price * p["quantity"]

        tax_amount = Decimal("0.00")
        total_final = items_total + tax_amount + Decimal(str(frais_livraison)) - Decimal(str(discount_amount))

        order = Order.objects.create(
            user=user,
            nom_client=nom_client,
            prenom_client=prenom_client,
            email_client=email_client,
            address_livraison=address_livraison,
            phone_livraison=phone_livraison,
            city=city,
            country=country,
            notes=notes,
            is_for_delivery=is_for_delivery,
            items_total=items_total,
            frais_livraison=Decimal(str(frais_livraison)),
            discount_amount=Decimal(str(discount_amount)),
            tax_amount=tax_amount,
            total_final=total_final,
        )

        order_items = []

        for item in items:
            variant = variants_cache[str(item["product_id"])]
            quantity = item["quantity"]
            subtotal = variant.price * quantity

            order_items.append(
                OrderItem(
                    order=order,
                    product=variant,                          # ← lié à la variante
                    product_name=f"{variant.product.name} — {variant.name}",
                    product_sku=variant.sku,
                    quantity=quantity,
                    unit_price=variant.price,
                    subtotal=subtotal,
                )
            )

            # Décrémentation immédiate du stock de la variante
            variant.stock -= quantity
            variant.save(update_fields=["stock"])

            produit_principal = variant.product
            if produit_principal:
                produit_principal.stock = max(0, produit_principal.stock - quantity)
                produit_principal.save(update_fields=["stock"])

        OrderItem.objects.bulk_create(order_items)

        # Création des packs commandés
        order_pack_items_to_create = []
        for p in packs:
            pack = packs_cache[str(p["pack_id"])]
            quantity = p["quantity"]
            subtotal = pack.price * quantity

            order_pack = OrderPack.objects.create(
                order=order,
                pack=pack,
                pack_name=pack.name,
                quantity=quantity,
                unit_price=pack.price,
                subtotal=subtotal
            )

            for pack_item in pack.items.select_related('product_variant').all():
                variant = pack_item.product_variant
                item_qty = pack_item.quantity * quantity

                order_pack_items_to_create.append(
                    OrderItem(
                        order=order,
                        product=variant,
                        product_name=f"{variant.product.name} — {variant.name} (Pack {pack.name})",
                        product_sku=variant.sku,
                        quantity=item_qty,
                        unit_price=Decimal("0.00"),
                        subtotal=Decimal("0.00"),
                        order_pack=order_pack
                    )
                )

            PackService.decrement_pack_stock(pack, quantity)
            
        if order_pack_items_to_create:
            OrderItem.objects.bulk_create(order_pack_items_to_create)

        OrderStatusHistory.objects.create(
            order=order,
            old_status="",
            new_status=order.status,
            comment="Commande créée.",
            changed_by=user if user else None,
        )

        return order

    @staticmethod
    @transaction.atomic
    def update_status(
        *,
        order,
        new_status,
        changed_by,
        comment="",
    ):
        """
        Changement de statut.
        """

        old_status = order.status

        order.status = new_status
        
        update_fields = ["status"]
        if new_status == OrderStatus.PAID and old_status != OrderStatus.PAID:
            order.paid_at = timezone.now()
            update_fields.append("paid_at")

        order.save(
            update_fields=update_fields
        )

        OrderStatusHistory.objects.create(
            order=order,
            old_status=old_status,
            new_status=new_status,
            comment=comment,
            changed_by=changed_by,
        )

        return order


class FactureEmailService:
    """
    Service gérant l'envoi des factures par email via SMTP.
    """

    @staticmethod
    def send_invoice_email(order: Order) -> bool:
        """
        Envoie un email HTML récapitulatif de la commande au client.
        """
        from django.core.mail import EmailMultiAlternatives
        from django.conf import settings
        from django.template.loader import render_to_string
        from django.utils.html import strip_tags

        if not order.user or not order.user.email:
            if not getattr(order, 'email_client', None):
                return False
            recipient_email = order.email_client
            client_first_name = order.prenom_client or ""
        else:
            recipient_email = order.user.email
            client_first_name = order.user.first_name

        subject = f"Facture de votre commande {order.numero_commande or order.reference}"
        
        # Contexte pour le template HTML
        context = {
            'order': order,
            'items': order.items.all(),
        }
        
        # Pour faire simple dans un premier temps, on va générer le corps directement
        # si on n'a pas de template HTML préparé.
        html_content = f"""
        <html>
            <body style="font-family: Arial, sans-serif; color: #333;">
                <h2 style="color: #1f4d3f;">Merci pour votre commande !</h2>
                <p>Bonjour {client_first_name},</p>
                <p>Votre commande <strong>{order.numero_commande or order.reference}</strong> a été payée avec succès.</p>
                <table style="width: 100%; border-collapse: collapse; margin-top: 20px;">
                    <thead>
                        <tr style="background-color: #f8faf8; border-bottom: 2px solid #1f4d3f;">
                            <th style="padding: 10px; text-align: left;">Produit</th>
                            <th style="padding: 10px; text-align: right;">Qté</th>
                            <th style="padding: 10px; text-align: right;">Prix</th>
                            <th style="padding: 10px; text-align: right;">Sous-total</th>
                        </tr>
                    </thead>
                    <tbody>
                        {"".join([f'''
                        <tr style="border-bottom: 1px solid #eee;">
                            <td style="padding: 10px;">{item.product_name}</td>
                            <td style="padding: 10px; text-align: right;">{item.quantity}</td>
                            <td style="padding: 10px; text-align: right;">{item.unit_price} FCFA</td>
                            <td style="padding: 10px; text-align: right;">{item.subtotal} FCFA</td>
                        </tr>
                        ''' for item in order.items.all()])}
                    </tbody>
                </table>
                <p style="text-align: right; margin-top: 20px;">
                    <strong>Total payé : {order.total_final} FCFA</strong>
                </p>
            </body>
        </html>
        """

        text_content = strip_tags(html_content)

        msg = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[recipient_email],
        )
        msg.attach_alternative(html_content, "text/html")
        
        try:
            msg.send(fail_silently=False)
            return True
        except Exception as e:
            # En environnement de production, on loggerait l'erreur
            print(f"Erreur d'envoi d'email : {e}")
            return False