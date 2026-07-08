"""
Service de recherche IA multi-tables — Atelier du Terroir.

Architecture :
  AISearchService
      ├─▶ _detect_intents()        — Détection des intentions via mots-clés
      ├─▶ _query_products()        — Produits, catégories, promotions (public)
      ├─▶ _query_orders()          — Commandes (customer + admin)
      ├─▶ _query_wallet()          — Wallet & transactions (customer + admin)
      ├─▶ _query_loyalty()         — Points de fidélité (customer + admin)
      ├─▶ _query_deliveries()      — Livraisons (customer + admin)
      ├─▶ _query_payments()        — Paiements (customer + admin)
      ├─▶ _query_admin_*()         — Données globales (admin uniquement)
      └─▶ _build_llm_summary()     — Synthèse pour le LLM + reformulation finale

@module apps.chatbot.search_service
"""
import json
import logging
import re
from decimal import Decimal
from typing import Any

import openai
from django.conf import settings
from django.db.models import Q, Sum, Avg, Count, F
from django.utils import timezone

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTES
# ─────────────────────────────────────────────────────────────────────────────

ROLE_ANONYMOUS = "anonymous"
ROLE_CUSTOMER = "customer"
ROLE_ADMIN = "platform_admin"

# Cartographie des intentions → mots-clés (FR + variantes)
INTENT_KEYWORDS: dict[str, list[str]] = {
    "products": [
        "produit", "article", "catalogue", "catégorie", "categorie", "image", "variante",
        "bio", "stock", "dispo", "prix", "top", "favori", "note", "mieux", "avis", "évaluation", "evaluation",
        "populaire", "tendance", "frais", "légume", "fruit", "huile", "épice",
        "spice", "tubercule", "feuille", "viande", "poisson", "lait", "fromage",
        "miel", "arachide", "céréale", "boisson", "jus", "farine", "piment", "savon",
        "recherche", "voir", "acheter", "liste", "tout", "tous", "rayon", "boutique", "magasin",
    ],
    "promos": [
        "promo", "promotion", "solde", "réduction", "reduction", "coupon",
        "code", "remise", "cadeau", "offert", "gratuit", "bon plan", "deal",
        "moins cher", "rabais", "avantage", "flash", "bannière",
    ],
    "orders": [
        "commande", "achat", "commander", "acheté", "order", "panier", "cart",
        "statut", "expédié", "annulé", "remboursé", "référence", "réf", "item", "article commandé",
        "récente", "dernière", "historique", "mes achats", "suivre ma commande",
    ],
    "wallet": [
        "wallet", "portefeuille", "solde", "recharge", "argent", "fonds", "cagnotte",
        "balance", "crédit", "compte", "débit", "transaction wallet", "historique wallet",
    ],
    "loyalty": [
        "fidélité", "fidelite", "points", "palier", "vip", "grade", "niveau", "statut vip",
        "bronze", "silver", "gold", "elite", "récompense", "avantage", "gain", "programme",
    ],
    "deliveries": [
        "livraison", "livreur", "suivi", "colis", "tracking", "adresse", "expédition",
        "délai", "délais", "estimée", "date de livraison", "frais de port", "transport",
        "livré", "en transit", "préparation", "zone", "pays", "ville", "expédition",
    ],
    "payments": [
        "paiement", "payé", "transaction", "facture", "paydunya", "mobile money",
        "virement", "cashback", "carte", "visa", "mastercard", "moyen de paiement",
        "règlement", "payer", "prix total", "tva", "taxe",
    ],
    "notifications": [
        "newsletter", "abonnement", "désabonnement", "contact", "message", "nous contacter",
        "support", "aide", "notification", "alerte", "mail", "email", "courriel", "question",
    ],
    "admin_users": [
        "utilisateur", "client", "inscription", "compte", "membre", "profil", "rôle", "permission",
        "tous les", "global", "plateforme", "admin", "administrateur", "gestion", "staff",
    ],
    "admin_stats": [
        "chiffre", "affaire", "revenu", "bénéfice", "statistique", "kpi", "métrique", "metric",
        "total", "résumé", "rapport", "dashboard", "vue globale", "ventes", "performance",
    ],
}


def _normalize(text: str) -> str:
    """Minuscule + suppression des accents pour la comparaison."""
    import unicodedata
    nfkd = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def _detect_intents(query: str) -> list[str]:
    """Retourne la liste des intentions détectées dans la requête."""
    q = _normalize(query)
    detected = []
    for intent, keywords in INTENT_KEYWORDS.items():
        for kw in keywords:
            if _normalize(kw) in q:
                detected.append(intent)
                break
    # Si aucune intention détectée → recherche produits par défaut
    if not detected:
        detected = ["products"]
    return detected


# ─────────────────────────────────────────────────────────────────────────────
# SERVICE PRINCIPAL
# ─────────────────────────────────────────────────────────────────────────────

class AISearchService:
    """
    Service de recherche IA contextuelle et sécurisée.

    Le service :
    1. Détermine le rôle de l'utilisateur
    2. Détecte les intentions dans la requête
    3. Exécute les requêtes ORM autorisées pour ce rôle
    4. Formate les résultats bruts
    5. Envoie le tout au LLM pour une reformulation naturelle et élégante

    Args:
        user: Instance User authentifiée, ou None pour un anonyme.
        query: Texte brut de la recherche.
    """

    def __init__(self, user=None, query: str = "") -> None:
        self.user = user
        self.query = query.strip()
        self.client = openai.OpenAI(
            api_key=settings.OPENAI_API_KEY,
            base_url=getattr(settings, "OPENAI_API_BASE", "https://api.openai.com/v1"),
        )
        self.model = getattr(settings, "OPENAI_MODEL", "openai/gpt-4o-mini")

        # Détermination du rôle
        if user is None:
            self.role = ROLE_ANONYMOUS
        elif getattr(user, "role", "") == "platform_admin":
            self.role = ROLE_ADMIN
        else:
            self.role = ROLE_CUSTOMER

    # =========================================================================
    #  POINT D'ENTRÉE
    # =========================================================================

    def search(self) -> dict:
        """
        Exécute la recherche et retourne { message, results_count, role }.

        Returns:
            dict avec 'message' (str formaté par le LLM), 'results_count' (int),
            'role' (str) et optionnellement 'conversation_id'.
        """
        if not self.query:
            return {
                "message": "Veuillez saisir une question ou un terme de recherche.",
                "results_count": 0,
                "role": self.role,
            }

        intents = _detect_intents(self.query)
        logger.info(
            "AISearchService: query=%r role=%s intents=%s",
            self.query, self.role, intents,
        )

        # Collecte des données selon les intentions et les permissions
        raw_data: dict[str, Any] = {}

        for intent in intents:
            if intent == "products":
                raw_data["products"] = self._query_products()

            elif intent == "promos":
                raw_data["promos"] = self._query_promos()

            elif intent == "orders" and self.role != ROLE_ANONYMOUS:
                raw_data["orders"] = self._query_orders()

            elif intent == "wallet" and self.role != ROLE_ANONYMOUS:
                raw_data["wallet"] = self._query_wallet()

            elif intent == "loyalty" and self.role != ROLE_ANONYMOUS:
                raw_data["loyalty"] = self._query_loyalty()

            elif intent == "deliveries" and self.role != ROLE_ANONYMOUS:
                raw_data["deliveries"] = self._query_deliveries()

            elif intent == "payments" and self.role != ROLE_ANONYMOUS:
                raw_data["payments"] = self._query_payments()

            elif intent == "notifications":
                raw_data["notifications"] = self._query_notifications()

            elif intent == "admin_users" and self.role == ROLE_ADMIN:
                raw_data["admin_users"] = self._query_admin_users()

            elif intent == "admin_stats" and self.role == ROLE_ADMIN:
                raw_data["admin_stats"] = self._query_admin_stats()

            # Si l'utilisateur demande des données privées mais n'est pas connecté
            elif intent in ("orders", "wallet", "loyalty", "deliveries", "payments") and self.role == ROLE_ANONYMOUS:
                raw_data["auth_required"] = True

        total_results = sum(
            len(v) if isinstance(v, list) else (1 if v and v is not True else 0)
            for v in raw_data.values()
        )

        message = self._build_llm_summary(raw_data)

        return {
            "message": message,
            "results_count": total_results,
            "role": self.role,
        }

    # =========================================================================
    #  REQUÊTES ORM — DONNÉES PUBLIQUES
    # =========================================================================

    def _query_promos(self) -> list[dict]:
        """Retourne la liste des codes promo actifs."""
        from apps.promotions.models import PromoCode
        from django.utils import timezone as tz

        now = tz.now()
        codes = PromoCode.objects.filter(
            is_active=True,
            valid_from__lte=now,
            valid_until__gte=now,
        ).order_by("valid_until")

        return [
            {
                "code": c.code,
                "type": c.discount_type,
                "value": f"{c.discount_value}",
                "min_purchase": f"{c.min_purchase_amount} FCFA" if c.min_purchase_amount else "Aucun",
                "until": c.valid_until.strftime("%d/%m/%Y"),
                "description": c.description or "",
            }
            for c in codes
        ]

    def _query_notifications(self) -> dict:
        """Retourne des informations générales de contact/newsletter, ou admin."""
        if self.role == ROLE_ADMIN:
            from apps.notifications.models import ContactMessage
            unread_count = ContactMessage.objects.filter(is_read=False).count()
            return {"admin_unread_messages": unread_count}
        return {
            "info": "Vous pouvez vous abonner à notre newsletter depuis le pied de page du site. Pour nous contacter, utilisez le formulaire de contact sur la page 'Contact'. Nos équipes vous répondront rapidement."
        }

    def _query_products(self) -> list[dict]:
        """Recherche de produits actifs correspondant à la requête."""
        from apps.catalog.models import Product, Category
        from apps.promotions.models import Soldes
        from django.utils import timezone as tz

        query = self.query

        # Détection de filtres spéciaux
        only_top = any(kw in _normalize(query) for kw in ["top", "tendance", "populaire"])
        only_promo = any(kw in _normalize(query) for kw in ["solde", "promo", "promotion", "reduction"])
        only_favorites = any(kw in _normalize(query) for kw in ["favori"])
        only_rated = any(kw in _normalize(query) for kw in ["note", "avis", "mieux note", "bien note"])

        qs = Product.objects.filter(is_active=True).select_related("category")

        if only_top:
            qs = qs.filter(is_top=True).order_by("-order_count", "-note_produit")
        elif only_promo:
            # Produits actuellement en solde
            now = tz.now()
            solde_product_ids = Soldes.objects.filter(
                is_active=True,
                starts_at__lte=now,
                ends_at__gte=now,
            ).values_list("product_id", flat=True)
            qs = qs.filter(id__in=solde_product_ids).order_by("-order_count")
        elif only_favorites:
            qs = qs.order_by("-count_favorites", "-note_produit")
        elif only_rated:
            qs = qs.filter(count_ratings__gt=0).order_by("-note_produit", "-count_ratings")
        else:
            # Recherche textuelle sur le nom, description, catégorie
            words = query.split()
            q_filter = Q()
            for word in words:
                q_filter |= (
                    Q(name__icontains=word)
                    | Q(description__icontains=word)
                    | Q(category__name__icontains=word)
                    | Q(sku__icontains=word)
                )
            qs = qs.filter(q_filter).order_by("-order_count", "-note_produit")

        products = qs[:8]

        # Enrichissement avec soldes actives
        now = tz.now()
        active_sales = {}
        if products:
            sales = Soldes.objects.filter(
                is_active=True,
                starts_at__lte=now,
                ends_at__gte=now,
                product__in=[p.id for p in products],
            ).select_related("product")
            for sale in sales:
                active_sales[str(sale.product_id)] = {
                    "sale_price": str(sale.sale_price),
                    "discount_percent": sale.discount_percent,
                    "ends_at": sale.ends_at.strftime("%d/%m/%Y %H:%M"),
                }

        result = []
        for p in products:
            sale_info = active_sales.get(str(p.id))
            item = {
                "id": str(p.id),
                "name": p.name,
                "category": p.category.name,
                "price": str(p.price),
                "stock": p.stock,
                "is_in_stock": p.is_in_stock,
                "is_top": p.is_top,
                "note": str(p.note_produit),
                "count_ratings": p.count_ratings,
                "count_favorites": p.count_favorites,
                "order_count": p.order_count,
                "url": f"/products/{p.slug}",
            }
            if sale_info:
                item["en_solde"] = True
                item["prix_solde"] = sale_info["sale_price"]
                item["remise"] = f"{sale_info['discount_percent']}%"
                item["solde_fin"] = sale_info["ends_at"]
            result.append(item)

        return result

    # =========================================================================
    #  REQUÊTES ORM — DONNÉES CLIENT
    # =========================================================================

    def _query_orders(self) -> list[dict]:
        """Commandes de l'utilisateur (ou toutes pour admin)."""
        from apps.commandes.models import Order

        qs = Order.objects.select_related("delivery").prefetch_related("items")
        if self.role != ROLE_ADMIN:
            qs = qs.filter(user=self.user)

        # Filtre par statut si mentionné dans la query
        status_map = {
            "livré": "delivered",
            "payé": "paid",
            "expédié": "shipped",
            "annulé": "cancelled",
            "en cours": "processing",
            "en attente": "pending_payment",
        }
        q_norm = _normalize(self.query)
        for fr, en in status_map.items():
            if _normalize(fr) in q_norm:
                qs = qs.filter(status=en)
                break

        orders = qs.order_by("-created_at")[:5]

        result = []
        for o in orders:
            delivery = getattr(o, "delivery", None)
            result.append({
                "reference": o.reference or str(o.id)[:8],
                "status": o.get_status_display() if hasattr(o, "get_status_display") else o.status,
                "total_final": str(o.total_final),
                "date": o.created_at.strftime("%d/%m/%Y"),
                "ville": o.city,
                "nb_articles": o.items.count(),
                "livraison": {
                    "statut": delivery.get_status_display() if delivery and hasattr(delivery, "get_status_display") else (delivery.status if delivery else "—"),
                    "estimation": delivery.estimated_delivery_date.strftime("%d/%m/%Y") if delivery and delivery.estimated_delivery_date else "Non renseignée",
                } if delivery else None,
                "url": f"/customer/commandes/{o.reference}",
            })
        return result

    def _query_wallet(self) -> dict:
        """Wallet et dernières transactions de l'utilisateur."""
        from apps.paiements.models import Wallet, WalletTransaction

        try:
            wallet = Wallet.objects.get(user=self.user)
        except Wallet.DoesNotExist:
            return {"error": "Aucun wallet trouvé."}

        transactions = WalletTransaction.objects.filter(
            wallet=wallet,
        ).order_by("-created_at")[:5]

        return {
            "balance": str(wallet.balance),
            "status": wallet.status,
            "transactions": [
                {
                    "type": t.get_transaction_type_display() if hasattr(t, "get_transaction_type_display") else t.transaction_type,
                    "amount": str(t.amount),
                    "status": t.status,
                    "date": t.created_at.strftime("%d/%m/%Y"),
                }
                for t in transactions
            ],
            "url": "/customer/wallet",
        }

    def _query_loyalty(self) -> dict:
        """Points de fidélité et palier de l'utilisateur."""
        from apps.fidelites.models import LoyaltyProfile, LoyaltyEvent

        try:
            profile = LoyaltyProfile.objects.select_related("tier").get(user=self.user)
        except LoyaltyProfile.DoesNotExist:
            return {"error": "Aucun profil fidélité trouvé."}

        recent_events = LoyaltyEvent.objects.filter(
            user=self.user,
        ).order_by("-created_at")[:3]

        return {
            "points_balance": profile.points_balance,
            "total_points_gagne": profile.total_points_gagne,
            "total_solde": str(profile.total_solde),
            "palier": profile.tier.name if profile.tier else "Aucun",
            "reduction_palier": str(profile.tier.discount_percent) + "%" if profile.tier else "0%",
            "derniers_events": [
                {
                    "delta": f"{'+' if e.points_delta >= 0 else ''}{e.points_delta} pts",
                    "raison": e.get_reason_display() if hasattr(e, "get_reason_display") else e.reason,
                    "solde_apres": e.new_points_balance_after,
                    "date": e.created_at.strftime("%d/%m/%Y"),
                }
                for e in recent_events
            ],
            "url": "/customer/fidelite",
        }

    def _query_deliveries(self) -> list[dict]:
        """Livraisons liées aux commandes de l'utilisateur."""
        from apps.livraisons.models import Delivery

        qs = Delivery.objects.select_related("order")
        if self.role != ROLE_ADMIN:
            qs = qs.filter(order__user=self.user)

        deliveries = qs.order_by("-created_at")[:5]

        return [
            {
                "commande": d.order.reference or str(d.order.id)[:8],
                "statut": d.get_status_display() if hasattr(d, "get_status_display") else d.status,
                "adresse": d.delivery_address or d.order.address_livraison,
                "tracking": d.tracking_number or "Non disponible",
                "estimation": d.estimated_delivery_date.strftime("%d/%m/%Y") if d.estimated_delivery_date else "—",
                "livraison_effective": d.actual_delivery_date.strftime("%d/%m/%Y") if d.actual_delivery_date else "—",
            }
            for d in deliveries
        ]

    def _query_payments(self) -> list[dict]:
        """Paiements de l'utilisateur."""
        from apps.paiements.models import Payment

        qs = Payment.objects.filter(user=self.user).order_by("-created_at")[:5]

        return [
            {
                "type": p.get_payment_type_display() if hasattr(p, "get_payment_type_display") else p.payment_type,
                "montant": str(p.amount),
                "provider": p.get_provider_display() if hasattr(p, "get_provider_display") else p.provider,
                "statut": p.get_status_display() if hasattr(p, "get_status_display") else p.status,
                "date": p.created_at.strftime("%d/%m/%Y"),
            }
            for p in qs
        ]

    # =========================================================================
    #  REQUÊTES ORM — DONNÉES ADMIN
    # =========================================================================

    def _query_admin_users(self) -> list[dict]:
        """Liste des derniers utilisateurs (admin uniquement)."""
        from django.contrib.auth import get_user_model
        User = get_user_model()

        users = User.objects.order_by("-created_at")[:10]
        return [
            {
                "email": u.email,
                "nom": u.name,
                "role": u.role,
                "actif": u.is_active,
                "date_inscription": u.created_at.strftime("%d/%m/%Y"),
            }
            for u in users
        ]

    def _query_admin_stats(self) -> dict:
        """Statistiques globales de la plateforme (admin uniquement)."""
        from apps.commandes.models import Order
        from apps.paiements.models import Payment, Wallet
        from apps.catalog.models import Product
        from django.contrib.auth import get_user_model
        User = get_user_model()

        total_orders = Order.objects.count()
        total_revenue = Order.objects.filter(
            status__in=["paid", "confirmed", "processing", "shipped", "delivered"]
        ).aggregate(total=Sum("total_final"))["total"] or Decimal("0")

        total_products = Product.objects.filter(is_active=True).count()
        total_users = User.objects.filter(is_active=True).count()
        low_stock = Product.objects.filter(is_active=True, stock__lte=5).count()

        return {
            "total_commandes": total_orders,
            "chiffre_affaire_total": str(total_revenue),
            "total_produits_actifs": total_products,
            "total_clients_actifs": total_users,
            "produits_stock_faible": low_stock,
        }

    # =========================================================================
    #  REFORMULATION LLM
    # =========================================================================

    def _build_llm_summary(self, raw_data: dict) -> str:
        """
        Envoie les données brutes au LLM pour une reformulation élégante et claire.

        Si l'utilisateur n'est pas connecté et qu'une donnée privée a été demandée,
        retourne un message invitant à se connecter.
        """
        if raw_data.get("auth_required"):
            return (
                "🔒 Pour accéder à ces informations (commandes, wallet, fidélité...), "
                "vous devez être connecté à votre compte. "
                "Rendez-vous sur la page de connexion pour continuer."
            )

        if not raw_data:
            return (
                "Je n'ai trouvé aucun résultat correspondant à votre recherche. "
                "Essayez d'autres termes ou parcourez notre catalogue."
            )

        # Construction du contexte pour le LLM
        role_description = {
            ROLE_ANONYMOUS: "visiteur non connecté",
            ROLE_CUSTOMER: f"client connecté ({self.user.email})",
            ROLE_ADMIN: f"administrateur ({self.user.email})",
        }[self.role]

        data_summary = json.dumps(raw_data, ensure_ascii=False, indent=2, default=str)

        prompt = f"""Tu es l'assistant IA de "L'Atelier du Terroir", une épicerie fine en ligne.
L'utilisateur est un {role_description}.
Sa recherche : "{self.query}"

Voici les données récupérées depuis la base de données :
{data_summary}

Consignes de réponse :
- Réponds en français, de manière chaleureuse, claire et précise.
- Présente les résultats de manière structurée et lisible (listes, emojis pertinents).
- Pour les produits : indique le nom, le prix, le stock, la note et le lien.
- Pour les commandes : indique la référence, le statut, le total et la date.
- Pour le wallet : indique clairement le solde disponible et les dernières opérations.
- Pour la fidélité : indique les points et le palier actuel.
- Si des produits sont en solde, mets-le en avant.
- Utilise des emojis appropriés pour rendre la réponse visuellement agréable.
- Ajoute des liens cliquables vers les pages concernées.
- Si aucun résultat n'est trouvé dans une catégorie, mentionne-le brièvement.
- Ne répète jamais les données brutes JSON, reformule-les toujours en langage naturel.
- Termine toujours par une invitation à explorer ou une aide supplémentaire."""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "Tu es un assistant commercial IA expert de L'Atelier du Terroir."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.6,
                max_tokens=1500,
            )
            return response.choices[0].message.content or "Je n'ai pas pu formuler une réponse."
        except openai.RateLimitError:
            # Fallback : retour JSON formaté sans LLM
            return self._fallback_format(raw_data)
        except openai.OpenAIError as exc:
            logger.error("AISearchService: erreur LLM — %s", str(exc))
            return self._fallback_format(raw_data)

    def _fallback_format(self, raw_data: dict) -> str:
        """Format de secours si le LLM est indisponible."""
        lines = [f"🔍 Résultats pour : **{self.query}**\n"]

        if "products" in raw_data:
            products = raw_data["products"]
            if products:
                lines.append(f"📦 **{len(products)} produit(s) trouvé(s) :**")
                for p in products:
                    stock_icon = "✅" if p["is_in_stock"] else "❌"
                    lines.append(f"  • {p['name']} — {p['price']} FCFA {stock_icon} — [{p['url']}]({p['url']})")
            else:
                lines.append("📦 Aucun produit trouvé.")

        if "orders" in raw_data:
            orders = raw_data["orders"]
            if orders:
                lines.append(f"\n🛍️ **{len(orders)} commande(s) :**")
                for o in orders:
                    lines.append(f"  • {o['reference']} — {o['status']} — {o['total_final']} FCFA ({o['date']})")
            else:
                lines.append("\n🛍️ Aucune commande.")

        if "wallet" in raw_data:
            w = raw_data["wallet"]
            if "balance" in w:
                lines.append(f"\n💰 **Wallet :** {w['balance']} FCFA ({w['status']})")

        if "loyalty" in raw_data:
            loy = raw_data["loyalty"]
            if "points_balance" in loy:
                lines.append(f"\n⭐ **Fidélité :** {loy['points_balance']} pts — Palier : {loy['palier']}")

        lines.append("\n_Puis-je vous aider autrement ?_")
        return "\n".join(lines)
