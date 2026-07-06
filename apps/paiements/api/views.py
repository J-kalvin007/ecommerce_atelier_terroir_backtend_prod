import hashlib
import logging
from decimal import Decimal

from celery.worker.state import total_count
from django.conf import settings
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from paydunya import Store, Invoice, InvoiceItem
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.commandes.models import Order
from apps.paiements.models import Wallet, Payment, WalletTransaction

# Create and configure logger
logging.basicConfig(
    filename="newfile.log",
    format="%(name)s: %(asctime)s | %(levelname)s | %(filename)s%(lineno)s | %(process)d >>> %(message)s",  # noqa: E501
    filemode="w",
)

# Creating an object
logger = logging.getLogger()



@csrf_exempt
@api_view(["POST"])
@permission_classes([AllowAny])
def paydunya_webhook(request):
    logger.info("=== Webhook PayDunya reçu ===")

    data = request.POST.dict()

    token = data.get("data[invoice][token]")
    status_payment = data.get("data[status]")  # 'completed', 'pending', ou 'cancelled'
    description_payment = data.get("data[invoice][description]")  
    amount_payment_str = data.get("data[invoice][total_amount]")
    amount_payment = Decimal(str(amount_payment_str)) if amount_payment_str else Decimal("0.00")

    logger.info(f"Voici les données brute recues {data} - Détails de la transaction -> Token: {token}, Statut: {status_payment}, Description: {description_payment}, Montant: {amount_payment}")

    master_key = settings.PAYDUNYA_CONFIG["MASTER_KEY"].encode()

    if data.get("data[hash]") != hashlib.sha512(master_key).hexdigest():
        logger.error("SIGNATURE INVALIDE : Le hash reçu ne correspond pas.")
        return Response(
            {"error": "Signature invalide"},
            status=status.HTTP_403_FORBIDDEN,
        )

    # Traitement du statut de la commande
    if status_payment == "completed":
        logger.info("Statut de la transaction 'completed' validé.")

        if description_payment == "ACHAT-PRODUIT":
            logger.info("Traitement d'une transaction de type ACHAT-PRODUIT.")
            if not token:
                logger.error("Token de transaction manquant pour l'achat de produit.")
                return Response({"detail": "token de la transaction invalide"}, status=status.HTTP_400_BAD_REQUEST)

            order = get_object_or_404(Order, reference=token)
            logger.info(f"Commande trouvée pour le token {token} : {order.reference}.")
            
            with transaction.atomic():
                order.status = "paid"
                order.save()
                logger.info(f"Statut de la commande {order.reference} mis à jour avec succès : PAID.")

                # --- Décrémentation des stocks ---
                from apps.catalog.models import ProductVariant
                for item in order.items.all():
                    # 1. Chercher si la ligne correspond à une variation via le SKU
                    variant = ProductVariant.objects.filter(sku=item.product_sku).first()
                    
                    if variant:
                        ancien_stock = variant.stock
                        variant.stock = max(0, variant.stock - item.quantity)
                        variant.save()
                        logger.info(f"Stock de la variante '{variant.name}' (SKU: {variant.sku}) décrémenté : {ancien_stock} -> {variant.stock}")
                        
                        produit_principal = variant.product
                        if produit_principal:
                            ancien_stock_p = produit_principal.stock
                            produit_principal.stock = max(0, produit_principal.stock - item.quantity)
                            produit_principal.save()
                            logger.info(f"Stock du produit '{produit_principal.name}' (SKU: {produit_principal.sku}) décrémenté : {ancien_stock_p} -> {produit_principal.stock}")
                    else:
                        # 2. Si aucune variation ne correspond, on décrémente le produit principal
                        produit_principal = item.product
                        if produit_principal:
                            ancien_stock = produit_principal.stock
                            produit_principal.stock = max(0, produit_principal.stock - item.quantity)
                            produit_principal.save()
                            logger.info(f"Stock du produit '{produit_principal.name}' (SKU: {produit_principal.sku}) décrémenté : {ancien_stock} -> {produit_principal.stock}")
                        else:
                            logger.warning(f"Impossible de décrémenter le stock : aucun produit/variante trouvé pour le SKU {item.product_sku}")

                Payment.objects.create(
                    order=order,
                    user=order.user,
                    provider=Payment.Provider.PAYDUNYA,
                    payment_type=Payment.PaymentType.ORDER_PAYMENT,
                    amount=amount_payment,
                    status=Payment.Status.SUCCESS,
                    reference_externe=token,
                )
                logger.info(f"Ligne de paiement globale enregistrée avec succès pour la commande {order.reference}.")

            return Response(
                {"message": "Commande validée avec succès"},
                status=status.HTTP_200_OK,
            )

        elif description_payment == "RECHARGE-WALLET":
            logger.info("Traitement d'une transaction de type RECHARGE-WALLET.")
            if not token:
                logger.error("Token de transaction manquant pour la recharge de wallet.")
                return Response({"detail": "token de la transaction invalide"}, status=status.HTTP_400_BAD_REQUEST)

            wallet = get_object_or_404(Wallet, reference=token)
            logger.info(f"Wallet trouvé pour le token {token}. Solde actuel : {wallet.balance}.")
            
            with transaction.atomic():
                solde = wallet.balance
                wallet.balance = solde + amount_payment
                wallet.save()
                logger.info(f"Wallet {wallet.reference} crédité avec succès. Nouveau solde : {wallet.balance}.")

                WalletTransaction.objects.create(
                    wallet=wallet,
                    transaction_type=WalletTransaction.Type.DEPOSIT,
                    amount=amount_payment,
                    reference=token,
                    status=WalletTransaction.Status.SUCCESS,
                )
                logger.info(f"Transaction de wallet (WalletTransaction) créée avec succès pour {wallet.reference}.")

                Payment.objects.create(
                    wallet=wallet,
                    user=wallet.user,
                    provider=Payment.Provider.PAYDUNYA,
                    payment_type=Payment.PaymentType.WALLET_TOPUP,
                    amount=amount_payment,
                    status=Payment.Status.SUCCESS,
                    reference_externe=token,
                )
                logger.info(f"Paiement global enregistré avec succès pour la recharge de {wallet.reference}.")

            return Response(
                {"message": "Recharge validée avec succès"},
                status=status.HTTP_200_OK,
            )

        else:
            logger.warning(f"Description de paiement non reconnue : {description_payment}.")

    elif status_payment == "cancelled":
        logger.warning(f"La transaction {token} a été annulée.")
        return Response(
            {"message": "Statut de paiement annulé traité"},
            status=status.HTTP_200_OK,
        )

    logger.warning(f"Statut de transaction ignoré : {status_payment}")
    return Response(
        {"message": f"statut ignoré : {status_payment}"},
        status=status.HTTP_200_OK,
    )


class InitializePaydunyaPaymentView(APIView):
    def post(self, request, *args, **kwargs):

        # Recuperation des donnees de la commande
        order_id = request.data.get("order_id")
        description = request.data.get("description")

        if not order_id:
            return Response({"detail": "order_id invalide"}, status=status.HTTP_400_BAD_REQUEST)

        order = get_object_or_404(Order, id=order_id)
        logger.info(f"[Initialisation de paiement] Commande trouvée: {order.reference}")
        total_amount = float(order.total_final)

        # 1. Initialiser le magasin
        store = Store(
            name="Atelier du Terroir",
        )

        # 2. Créer la facture
        invoice = Invoice(store)

        invoice.description = "ACHAT-PRODUIT"

        # 3. Ajouter le montant total ou des articles (obligatoire pour PayDunya)
        invoice.total_amount = total_amount  # Définit le montant direct de la facture

        # 4. Configurer les URLs de redirection
        invoice.cancel_url = settings.PAYDUNYA_CANCEL_URL
        invoice.return_url = settings.PAYDUNYA_RETURN_URL
        invoice.callback_url = settings.PAYDUNYA_CALLBACK_URL

        # 5. Envoyer la demande à l'API PayDunya
        # La méthode 'create' renvoie un tuple (booléen_succès, infos_ou_erreur)
        success, response_or_error = invoice.create()

        if success:
            order.reference = response_or_error.get(
                "token",
            )
            order.save()
            return Response(
                {
                    "success": True,
                    "order_id": order_id,
                    "payment_url": response_or_error.get(
                        "response_text",
                    ),  # URL vers laquelle rediriger l'utilisateur
                    "token": order.reference,  # ID unique de la transaction à sauvegarder
                },
                status=status.HTTP_200_OK,
            )
        return Response(
            {
                "success": False,
                "error": response_or_error,
            },
            status=status.HTTP_400_BAD_REQUEST,
        )



class RechargeWalletPaydunyaPaymentView(APIView):
    def post(self, request, *args, **kwargs):

        # Recuperation des donnees de la commande
        wallet_id = request.data.get("order_id")
        description = request.data.get("description")
        montant = request.data.get("amount")

        if not wallet_id:
            return Response({"detail": "wallet_id invalide"}, status=status.HTTP_400_BAD_REQUEST)

        wallet = get_object_or_404(Wallet, id=wallet_id)
        logger.info(f"[Recharge de wallet] Wallet trouvée: {wallet.reference}")

        if not montant:
            return Response({"detail": "Montant a credite invalide"}, status=status.HTTP_400_BAD_REQUEST)

        if not description:
            return Response({"detail": "Description obligatoire"}, status=status.HTTP_400_BAD_REQUEST)

        logger.info(f"[Initialisation de paiement] Recharge du wallet du client avec le montant: {montant}")
        total_amount = float(montant)

        # 1. Initialiser le magasin
        store = Store(
            name="Atelier du Terroir",
        )

        # 2. Créer la facture
        invoice = Invoice(store)

        invoice.description = "RECHARGE-WALLET"

        # 3. Ajouter le montant total ou des articles (obligatoire pour PayDunya)
        invoice.total_amount = total_amount  # Définit le montant direct de la facture

        # 4. Configurer les URLs de redirection
        invoice.cancel_url = settings.PAYDUNYA_WALLET_CANCEL_URL
        invoice.return_url = settings.PAYDUNYA_WALLET_SUCCESS_URL
        invoice.callback_url = settings.PAYDUNYA_CALLBACK_URL

        # 5. Envoyer la demande à l'API PayDunya
        # La méthode 'create' renvoie un tuple (booléen_succès, infos_ou_erreur)
        success, response_or_error = invoice.create()

        if success:
            wallet.reference = response_or_error.get(
                "token",
            )
            wallet.save()
            return Response(
                {
                    "success": True,
                    "wallet_id": wallet_id,
                    "payment_url": response_or_error.get(
                        "response_text",
                    ),  # URL vers laquelle rediriger l'utilisateur
                    "token": wallet.reference,  # ID unique de la transaction à sauvegarder
                },
                status=status.HTTP_200_OK,
            )
        return Response(
            {
                "success": False,
                "error": response_or_error,
            },
            status=status.HTTP_400_BAD_REQUEST,
        )
