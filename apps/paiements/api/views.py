import hashlib
import hmac
import logging
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.db import transaction
from django.db.models import F
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from paydunya import Store, Invoice
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.commandes.models import Order, OrderStatus
from apps.commandes.services import OrderService
from apps.paiements.exceptions import PaymentGatewayError
from apps.paiements.gateways.paydunya import PayDunyaGateway
from apps.paiements.models import Wallet, Payment, WalletTransaction

# Logger nommé, câblé sur la configuration LOGGING de Django (console + Sentry).
# L'ancien logging.basicConfig(filename="newfile.log", filemode="w") détournait le
# logger racine, écrasait le journal à chaque import et privait la production de
# toute trace de paiement exploitable.
logger = logging.getLogger(__name__)


# Statuts de commande à partir desquels un paiement peut encore être initié.
PAYABLE_ORDER_STATUSES = (OrderStatus.DRAFT, OrderStatus.PENDING_PAYMENT)


def _is_platform_admin(user) -> bool:
    """Indique si l'utilisateur dispose des droits d'administration plateforme."""
    return bool(
        user
        and user.is_authenticated
        and (user.is_superuser or getattr(user, "role", None) == "platform_admin")
    )


def _assert_can_act_on_order(request, order) -> Response | None:
    """
    Vérifie que l'appelant a le droit d'agir sur `order`.

    Règle métier :
      - commande invité (order.user is None) : accessible via son identifiant,
        le parcours de paiement sans compte doit rester possible ;
      - commande rattachée à un compte : réservée à son propriétaire et aux
        administrateurs plateforme.

    Returns:
        Response d'erreur si l'accès doit être refusé, None si l'accès est permis.
    """
    if order.user_id is None:
        return None

    user = request.user
    if not user.is_authenticated:
        logger.warning(
            "[IDOR] Tentative anonyme sur la commande %s (propriétaire %s).",
            order.pk,
            order.user_id,
        )
        return Response(
            {"detail": "Vous devez être connecté pour accéder à cette commande."},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    if order.user_id != user.id and not _is_platform_admin(user):
        logger.warning(
            "[IDOR] Utilisateur %s a tenté d'accéder à la commande %s appartenant à %s.",
            user.id,
            order.pk,
            order.user_id,
        )
        return Response(
            {"detail": "Cette commande ne vous appartient pas."},
            status=status.HTTP_403_FORBIDDEN,
        )

    return None


def _to_decimal(raw_value) -> Decimal:
    """Convertit une valeur de montant hétérogène (str, int, float) en Decimal sûr."""
    if raw_value in (None, ""):
        return Decimal("0.00")
    try:
        return Decimal(str(raw_value)).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError, TypeError):
        logger.error("Montant illisible reçu de PayDunya : %r", raw_value)
        return Decimal("0.00")


@csrf_exempt
@api_view(["POST"])
@permission_classes([AllowAny])
def paydunya_webhook(request):
    """
    IPN PayDunya — POST /api/v1/paiements/ipn/

    Chaîne de confiance appliquée, dans cet ordre :

      1. Contrôle du hash `sha512(MASTER_KEY)` en comparaison à temps constant.
         Downgrade en WARNING en mode test (PayDunya test IPN n'envoie pas toujours le hash).
      2. Extraction du token depuis le payload (JSON ou form-encoded).
      3. Idempotence : si un Payment SUCCESS existe déjà pour ce token, on sort
         immédiatement en 200 (un rejeu ne doit jamais recréditer ni redébiter).
      4. Vérification serveur→serveur auprès de PayDunya (`verify_payment`).
         C'est la SEULE source de vérité : statut, montant et description sont
         relus depuis l'API, jamais depuis le corps du POST.
      5. Traitement métier sous transaction + verrou pessimiste sur la ligne
         Order/Wallet concernée.
    """
    logger.info("=== Webhook PayDunya reçu ===")
    logger.info("[IPN] Content-Type: %s", request.content_type)
    logger.info("[IPN] Payload brut: %s", request.data)

    # ── Extraction du payload : PayDunya peut envoyer JSON ou form-encoded ────
    # request.data est déjà parsé par DRF (JSON ou form selon Content-Type)
    raw = request.data

    # PayDunya IPN format : les données peuvent être dans raw["data"] (form-encoded)
    # ou directement à la racine (JSON). On supporte les deux.
    if "data" in raw and isinstance(raw["data"], dict):
        # Format JSON structuré : {"data": {"invoice": {...}, "status": "...", "hash": "..."}}
        ipn_data = raw["data"]
        token = (ipn_data.get("invoice") or {}).get("token")
        status_payment = ipn_data.get("status")
        description_payment = (ipn_data.get("invoice") or {}).get("description")
        amount_payment_str = (ipn_data.get("invoice") or {}).get("total_amount")
        received_hash = ipn_data.get("hash") or ""
    else:
        # Format form-encoded (clés bracket notation) ou JSON plat
        ipn_data = raw if isinstance(raw, dict) else {}
        token = (
            ipn_data.get("data[invoice][token]")
            or (ipn_data.get("invoice") or {}).get("token")
            or ipn_data.get("token")
        )
        status_payment = ipn_data.get("data[status]") or ipn_data.get("status")
        description_payment = (
            ipn_data.get("data[invoice][description]")
            or (ipn_data.get("invoice") or {}).get("description")
        )
        amount_payment_str = (
            ipn_data.get("data[invoice][total_amount]")
            or (ipn_data.get("invoice") or {}).get("total_amount")
        )
        received_hash = ipn_data.get("data[hash]") or ipn_data.get("hash") or ""

    amount_payment = _to_decimal(amount_payment_str)
    is_test_mode = getattr(settings, "PAYDUNYA_MODE", "test") == "test"

    logger.info(
        "[IPN] Notification parsée — Token: %s | Statut: %s | Description: %s | Montant: %s",
        token,
        status_payment,
        description_payment,
        amount_payment,
    )

    # ── 1. Contrôle du hash partagé ──────────────────────────────────────────
    master_key = settings.PAYDUNYA_CONFIG["MASTER_KEY"].encode()
    expected_hash = hashlib.sha512(master_key).hexdigest()

    hash_valid = received_hash and hmac.compare_digest(received_hash, expected_hash)
    if not hash_valid:
        if is_test_mode:
            # En mode test, PayDunya n'envoie pas toujours le hash : on log et on continue
            logger.warning(
                "[IPN] Hash manquant ou invalide (mode TEST — traitement poursuivi). "
                "Reçu: %r | Attendu: %r",
                received_hash,
                expected_hash,
            )
        else:
            logger.error(
                "[IPN] SIGNATURE INVALIDE en mode LIVE. Reçu: %r | Attendu: %r",
                received_hash,
                expected_hash,
            )
            return Response(
                {"error": "Signature invalide"},
                status=status.HTTP_403_FORBIDDEN,
            )

    # ── 2. Token obligatoire ──────────────────────────────────────────────────
    if not token:
        logger.error("[IPN] Token de transaction manquant dans la notification.")
        return Response(
            {"detail": "token de la transaction invalide"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # ── 3. Idempotence : ce token a-t-il déjà été encaissé ? ─────────────────
    if Payment.objects.filter(
        reference_externe=token,
        status=Payment.Status.SUCCESS,
    ).exists():
        logger.info(
            "[IPN] Notification ignorée : le token %s a déjà été traité avec succès.",
            token,
        )
        return Response(
            {"message": "Transaction déjà traitée"},
            status=status.HTTP_200_OK,
        )

    # ── 4. Vérification serveur→serveur : seule source de vérité ─────────────
    try:
        verification = PayDunyaGateway().verify_payment(token)
    except PaymentGatewayError as exc:
        logger.error(
            "[IPN] Vérification PayDunya impossible pour le token %s : %s", token, exc,
        )
        return Response(
            {"detail": "Vérification du paiement auprès de PayDunya impossible."},
            status=status.HTTP_502_BAD_GATEWAY,
        )

    verified_status = verification.get("status")
    verified_raw = verification.get("raw") or {}
    verified_invoice = verified_raw.get("invoice") or {}
    verified_description = verified_invoice.get("description") or ""
    verified_amount = _to_decimal(verification.get("amount"))

    logger.info(
        "[IPN] Vérification PayDunya — Token: %s | Statut vérifié: %s | "
        "Description: %s | Montant vérifié: %s",
        token,
        verified_status,
        verified_description,
        verified_amount,
    )

    if verified_status != "completed":
        logger.warning(
            "[IPN] Statut vérifié non finalisé pour le token %s : %s (annoncé : %s).",
            token,
            verified_status,
            status_payment,
        )
        return Response(
            {"message": f"statut ignoré : {verified_status}"},
            status=status.HTTP_200_OK,
        )

    # ── 5. Traitement métier, piloté par les données vérifiées ───────────────
    if verified_description == "ACHAT-PRODUIT":
        return _handle_verified_order_payment(token, verified_amount)

    if verified_description == "RECHARGE-WALLET":
        return _handle_verified_wallet_topup(token, verified_amount)

    logger.warning(
        "[IPN] Description de paiement non reconnue pour le token %s : %r.",
        token,
        verified_description,
    )
    return Response(
        {"message": f"description ignorée : {verified_description}"},
        status=status.HTTP_200_OK,
    )


def _handle_verified_order_payment(token: str, verified_amount: Decimal) -> Response:
    """
    Encaisse une commande dont le paiement a été confirmé par PayDunya.

    Le stock N'EST PAS décrémenté ici : il l'a déjà été au moment de la création
    de la commande (OrderService.create_order), qui est le point unique de
    réservation du stock. Le décrémenter une seconde fois au paiement doublait
    la consommation de stock de chaque commande payée.
    """
    logger.info("Traitement d'une transaction vérifiée de type ACHAT-PRODUIT.")

    with transaction.atomic():
        # Verrou pessimiste : sérialise deux notifications concurrentes portant
        # sur la même commande (rejeu réseau de PayDunya).
        order = Order.objects.select_for_update().filter(reference=token).first()

        if order is None:
            logger.error("Aucune commande ne porte la référence %s.", token)
            return Response(
                {"detail": "Commande introuvable pour ce token."},
                status=status.HTTP_404_NOT_FOUND,
            )

        logger.info("Commande trouvée pour le token %s : %s.", token, order.reference)

        # Seconde barrière d'idempotence, à l'intérieur du verrou.
        if order.status == OrderStatus.PAID:
            logger.info(
                "Commande %s déjà au statut PAID : notification ignorée.",
                order.reference,
            )
            return Response(
                {"message": "Commande déjà validée"},
                status=status.HTTP_200_OK,
            )

        # Contrôle du montant : un encaissement inférieur au dû ne valide pas la
        # commande. Le montant retenu est celui confirmé par PayDunya.
        if verified_amount < order.total_final:
            logger.error(
                "Sous-paiement détecté sur la commande %s : %s FCFA encaissés "
                "pour %s FCFA attendus.",
                order.reference,
                verified_amount,
                order.total_final,
            )
            return Response(
                {"detail": "Montant encaissé inférieur au montant de la commande."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        OrderService.update_status(
            order=order,
            new_status=OrderStatus.PAID,
            changed_by=None,
            comment="Paiement validé par PayDunya (vérifié côté serveur)",
        )
        logger.info(
            "Statut de la commande %s mis à jour avec succès : PAID.", order.reference,
        )

        Payment.objects.create(
            order=order,
            user=order.user,
            provider=Payment.Provider.PAYDUNYA,
            payment_type=Payment.PaymentType.ORDER_PAYMENT,
            amount=verified_amount,
            status=Payment.Status.SUCCESS,
            reference_externe=token,
        )
        logger.info(
            "Ligne de paiement globale enregistrée avec succès pour la commande %s.",
            order.reference,
        )

    return Response(
        {"message": "Commande validée avec succès"},
        status=status.HTTP_200_OK,
    )


def _handle_verified_wallet_topup(token: str, verified_amount: Decimal) -> Response:
    """Crédite un portefeuille dont la recharge a été confirmée par PayDunya."""
    logger.info("Traitement d'une transaction vérifiée de type RECHARGE-WALLET.")

    if verified_amount <= Decimal("0.00"):
        logger.error("Montant de recharge nul ou négatif pour le token %s.", token)
        return Response(
            {"detail": "Montant de recharge invalide."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    with transaction.atomic():
        wallet = Wallet.objects.select_for_update().filter(reference=token).first()

        if wallet is None:
            logger.error("Aucun portefeuille ne porte la référence %s.", token)
            return Response(
                {"detail": "Portefeuille introuvable pour ce token."},
                status=status.HTTP_404_NOT_FOUND,
            )

        logger.info(
            "Wallet trouvé pour le token %s. Solde actuel : %s.",
            token,
            wallet.balance,
        )

        # Seconde barrière d'idempotence : `WalletTransaction.reference` est
        # unique en base, ce contrôle évite de heurter l'IntegrityError.
        if WalletTransaction.objects.filter(reference=token).exists():
            logger.info(
                "Recharge déjà enregistrée pour le token %s : notification ignorée.",
                token,
            )
            return Response(
                {"message": "Recharge déjà validée"},
                status=status.HTTP_200_OK,
            )

        # Incrément atomique côté base : aucune lecture-modification-écriture en
        # Python, donc aucune perte de mise à jour concurrente.
        wallet.balance = F("balance") + verified_amount
        wallet.save(update_fields=["balance", "updated_at"])
        wallet.refresh_from_db(fields=["balance"])
        logger.info(
            "Wallet %s crédité avec succès. Nouveau solde : %s.",
            wallet.reference,
            wallet.balance,
        )

        WalletTransaction.objects.create(
            wallet=wallet,
            transaction_type=WalletTransaction.Type.DEPOSIT,
            amount=verified_amount,
            reference=token,
            status=WalletTransaction.Status.SUCCESS,
        )
        logger.info(
            "Transaction de wallet (WalletTransaction) créée avec succès pour %s.",
            wallet.reference,
        )

        Payment.objects.create(
            wallet=wallet,
            user=wallet.user,
            provider=Payment.Provider.PAYDUNYA,
            payment_type=Payment.PaymentType.WALLET_TOPUP,
            amount=verified_amount,
            status=Payment.Status.SUCCESS,
            reference_externe=token,
        )
        logger.info(
            "Paiement global enregistré avec succès pour la recharge de %s.",
            wallet.reference,
        )

    return Response(
        {"message": "Recharge validée avec succès"},
        status=status.HTTP_200_OK,
    )


class InitializePaydunyaPaymentView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):

        # Recuperation des donnees de la commande
        order_id = request.data.get("order_id")

        if not order_id:
            return Response({"detail": "order_id invalide"}, status=status.HTTP_400_BAD_REQUEST)

        order = get_object_or_404(Order, id=order_id)

        # SÉCURITÉ — IDOR : la vue est publique pour permettre le paiement invité,
        # mais une commande rattachée à un compte n'est payable que par ce compte.
        permission_error = _assert_can_act_on_order(request, order)
        if permission_error is not None:
            return permission_error

        # Une commande déjà payée, expédiée ou annulée ne doit plus générer de
        # facture PayDunya : cela écraserait sa référence et ouvrirait la porte à
        # un second encaissement.
        if order.status not in PAYABLE_ORDER_STATUSES:
            return Response(
                {"detail": f"Cette commande ne peut plus être payée (statut : {order.status})."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        logger.info("[Initialisation de paiement] Commande trouvée: %s", order.reference)
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
            order.save(update_fields=["reference", "updated_at"])
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

        # SÉCURITÉ — IDOR : un utilisateur authentifié ne peut initier une recharge
        # que sur son propre portefeuille. Sans ce contrôle, n'importe qui pouvait
        # écraser la référence PayDunya du wallet d'un tiers et détourner l'IPN
        # de recharge correspondante.
        if wallet.user_id != request.user.id and not _is_platform_admin(request.user):
            logger.warning(
                "[IDOR] Utilisateur %s a tenté de recharger le portefeuille %s appartenant à %s.",
                request.user.id,
                wallet.pk,
                wallet.user_id,
            )
            return Response(
                {"detail": "Ce portefeuille ne vous appartient pas."},
                status=status.HTTP_403_FORBIDDEN,
            )

        logger.info("[Recharge de wallet] Wallet trouvée: %s", wallet.reference)

        if not montant:
            return Response({"detail": "Montant a credite invalide"}, status=status.HTTP_400_BAD_REQUEST)

        if not description:
            return Response({"detail": "Description obligatoire"}, status=status.HTTP_400_BAD_REQUEST)

        # Le montant provient du client : il doit être numérique et strictement positif.
        montant_decimal = _to_decimal(montant)
        if montant_decimal <= Decimal("0.00"):
            return Response({"detail": "Montant a credite invalide"}, status=status.HTTP_400_BAD_REQUEST)

        logger.info(
            "[Initialisation de paiement] Recharge du wallet du client avec le montant: %s",
            montant_decimal,
        )
        total_amount = float(montant_decimal)

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
            wallet.save(update_fields=["reference", "updated_at"])
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
