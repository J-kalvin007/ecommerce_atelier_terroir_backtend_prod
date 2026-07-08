"""
Service principal du Chatbot IA — Atelier du Terroir.

ChatService orchestre :
1. La gestion de l'historique de conversation (création / récupération).
2. La construction du contexte envoyé au LLM (prompt système + historique).
3. L'appel à l'API OpenAI avec le mécanisme de Function Calling.
4. L'exécution des actions internes (requêtes Django ORM directes).
5. La génération de la réponse finale en langage naturel.

Architecture :
  ChatView (views.py)
      └─▶ ChatService.process_message()
              ├─▶ _get_or_create_conversation()   — persistance
              ├─▶ _build_context()                 — fenêtre de 10 messages
              ├─▶ openai.chat.completions.create()  — appel LLM
              ├─▶ _call_api()                       — router de fonctions
              └─▶ openai.chat.completions.create()  — reformulation finale

@module apps.chatbot.services
"""
import json
import logging

import openai
from django.conf import settings

from .api_definitions import API_FUNCTIONS
from .models import Conversation, Message

logger = logging.getLogger(__name__)

# Nombre maximum de messages de l'historique envoyés au LLM.
# Limiter à 10 évite de dépasser la fenêtre de tokens et contrôle les coûts.
CONTEXT_WINDOW_SIZE = 10


class ChatService:
    """
    Orchestrateur principal du chatbot IA.

    Chaque requête HTTP crée une instance fraîche de ce service.
    Le service ne conserve pas d'état entre les requêtes — tout est
    chargé depuis la base de données via la conversation.

    Args:
        user: L'utilisateur Django authentifié, ou None pour un anonyme.
    """

    def __init__(self, user=None) -> None:
        self.user = user
        self.client = openai.OpenAI(
            api_key=settings.OPENAI_API_KEY,
            base_url=getattr(settings, "OPENAI_API_BASE", "https://api.openai.com/v1"),
        )
        self.model = getattr(settings, "OPENAI_MODEL", "openai/gpt-4o-mini")

    # ============================================================
    #  POINT D'ENTRÉE PUBLIC
    # ============================================================

    def process_message(
        self,
        user_message: str,
        conversation_id=None,
    ) -> dict:
        """
        Traite un message utilisateur et retourne la réponse de l'assistant IA.

        Étapes :
          1. Récupère ou crée la conversation.
          2. Sauvegarde le message utilisateur.
          3. Construit le contexte (prompt système + historique).
          4. Appel au LLM avec function calling.
          5. Si le LLM veut appeler une API → exécution → reformulation.
          6. Sauvegarde la réponse de l'assistant.
          7. Retourne { message, conversation_id }.

        Args:
            user_message    : Texte brut envoyé par l'utilisateur.
            conversation_id : UUID (str ou UUID) de la conversation à continuer.
                              None pour en créer une nouvelle.

        Returns:
            dict avec les clés 'message' (str) et 'conversation_id' (UUID).
        """
        # --- 1. Récupération ou création de la conversation ---
        conversation = self._get_or_create_conversation(conversation_id)

        # --- 2. Persistance du message utilisateur ---
        # On ne persiste pas les messages des utilisateurs anonymes
        # pour respecter la vie privée et éviter une croissance incontrôlée de la DB.
        if self.user:
            Message.objects.create(
                conversation=conversation,
                role=Message.Role.USER,
                content=user_message,
            )

        # --- 3. Construction du contexte à envoyer au LLM ---
        messages_for_llm = self._build_context(conversation, user_message)

        # --- 4. Premier appel au LLM (avec function calling activé) ---
        logger.info(
            "ChatService: appel OpenAI model=%s user=%s conversation=%s",
            self.model,
            self.user.email if self.user else "anonyme",
            str(conversation.id)[:8],
        )

        try:
            first_response = self.client.chat.completions.create(
                model=self.model,
                messages=messages_for_llm,
                tools=[{"type": "function", "function": fn} for fn in API_FUNCTIONS],
                tool_choice="auto",
                temperature=0.7,
                max_tokens=1000,
            )
        except openai.OpenAIError as exc:
            logger.error("ChatService: erreur OpenAI — %s", str(exc))
            raise

        assistant_message = first_response.choices[0].message

        # --- 5. Vérification si le LLM veut exécuter une fonction ---
        if assistant_message.tool_calls:
            # Le LLM a décidé d'appeler une ou plusieurs fonctions internes.
            # On exécute chaque appel et on renvoie les résultats au LLM
            # pour qu'il formule une réponse naturelle et enrichie.

            # On ajoute le message "tool_calls" du LLM au contexte
            messages_for_llm.append(assistant_message)

            for tool_call in assistant_message.tool_calls:
                function_name = tool_call.function.name
                function_args = json.loads(tool_call.function.arguments)

                logger.info(
                    "ChatService: exécution function_call name=%s args=%s",
                    function_name,
                    function_args,
                )

                # Exécution de la fonction Django interne
                api_result = self._call_api(function_name, function_args)

                # On ajoute le résultat au contexte avec le rôle "tool"
                messages_for_llm.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": api_result,
                })

            # Deuxième appel au LLM pour reformuler les résultats en langage naturel
            try:
                final_response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages_for_llm,
                    temperature=0.7,
                    max_tokens=1000,
                )
                final_text = final_response.choices[0].message.content or ""
            except openai.OpenAIError as exc:
                logger.error("ChatService: erreur reformulation — %s", str(exc))
                raise
        else:
            # Le LLM a répondu directement sans appeler de fonction
            final_text = assistant_message.content or ""

        # --- 6. Persistance de la réponse de l'assistant ---
        if self.user:
            Message.objects.create(
                conversation=conversation,
                role=Message.Role.ASSISTANT,
                content=final_text,
            )

        logger.info(
            "ChatService: réponse générée (%d caractères) conversation=%s",
            len(final_text),
            str(conversation.id)[:8],
        )

        # --- 7. Retour de la réponse au client ---
        return {
            "message": final_text,
            "conversation_id": conversation.id,
        }

    # ============================================================
    #  GESTION DE LA CONVERSATION
    # ============================================================

    def _get_or_create_conversation(self, conversation_id=None) -> Conversation:
        """
        Récupère une conversation existante par son UUID, ou en crée une nouvelle.

        Si le conversation_id ne correspond à aucune conversation de cet utilisateur
        (ou si l'utilisateur est anonyme), une nouvelle conversation est créée.

        Args:
            conversation_id: UUID de la conversation à récupérer.

        Returns:
            Instance Conversation (existante ou nouvellement créée).
        """
        if conversation_id and self.user:
            # On cherche la conversation dans le scope de l'utilisateur
            # pour éviter qu'un utilisateur accède à la conversation d'un autre.
            try:
                return Conversation.objects.get(
                    id=conversation_id,
                    user=self.user,
                )
            except Conversation.DoesNotExist:
                logger.warning(
                    "ChatService: conversation %s introuvable pour user %s — création d'une nouvelle.",
                    conversation_id,
                    self.user.email,
                )

        # Création d'une nouvelle conversation
        return Conversation.objects.create(user=self.user)

    # ============================================================
    #  CONSTRUCTION DU CONTEXTE LLM
    # ============================================================

    def _build_context(self, conversation: Conversation, current_message: str) -> list[dict]:
        """
        Construit la liste de messages à envoyer au LLM.

        Structure :
          [0]   System prompt (rôle et instructions de l'assistant)
          [1..] Historique des N derniers messages de la conversation
          [-1]  Message courant de l'utilisateur (si anonyme, il n'est pas en DB)

        On limite l'historique à CONTEXT_WINDOW_SIZE messages pour :
          - Contrôler les coûts (facturation au token)
          - Éviter de dépasser la fenêtre de contexte du modèle

        Args:
            conversation    : La conversation dont on extrait l'historique.
            current_message : Le message courant de l'utilisateur.

        Returns:
            Liste de dicts au format messages OpenAI.
        """
        context: list[dict] = [
            {"role": "system", "content": self._build_system_prompt()},
        ]

        if self.user:
            # L'utilisateur est authentifié — on charge l'historique depuis la DB.
            # On exclut le dernier message (le courant) qui vient d'être ajouté.
            history = (
                Message.objects
                .filter(conversation=conversation)
                .order_by("-created_at")[:CONTEXT_WINDOW_SIZE]
            )
            # On inverse pour avoir l'ordre chronologique correct
            for msg in reversed(list(history)):
                context.append({"role": msg.role, "content": msg.content})
        else:
            # Utilisateur anonyme — aucun historique en DB,
            # on ajoute directement le message courant.
            context.append({"role": "user", "content": current_message})

        return context

    def _build_system_prompt(self) -> str:
        """
        Construit le prompt système personnalisé selon le contexte utilisateur.

        Le prompt système définit :
        - Le rôle et la personnalité de l'assistant
        - Les capacités disponibles
        - L'identité de l'utilisateur connecté (si authentifié)
        - Les instructions de formatage des réponses
        - Les CONTRAINTES STRICTES sur les moyens de paiement et la devise

        Returns:
            Chaîne de caractères du prompt système.
        """
        base_prompt = """Tu es l'assistant commercial IA de "L'Atelier du Terroir", \
une épicerie fine en ligne spécialisée dans les produits alimentaires du terroir africain.

Ton rôle est d'aider les clients avec :
- La recherche et la découverte de produits (fruits, légumes, huiles, feuilles, tubercules...)
- Les informations sur les catégories de produits disponibles
- Le suivi de leurs commandes et l'état des livraisons
- La consultation de leur solde de porte-monnaie (wallet)
- Leurs points de fidélité et leur grade actuel

═══════════════════════════════════════════════════════════
RÈGLES ABSOLUES ET NON NÉGOCIABLES (INTERDICTION DE DÉROGER)
═══════════════════════════════════════════════════════════

1. MOYENS DE PAIEMENT — LISTE BLANCHE EXCLUSIVE :
   Les SEULS moyens de paiement acceptés sur cette plateforme sont :
   a) Le WALLET ÉLECTRONIQUE personnel de l'utilisateur (solde disponible dans son compte)
   b) Le MOBILE MONEY (paiement par téléphone mobile)
   c) La CARTE BANCAIRE, via notre agrégateur de paiement agréé PAYDUNYA

   ⛔ INTERDIT ABSOLU : Ne JAMAIS mentionner PayPal, Stripe, Virement bancaire,
      Chèque, Bitcoin, Cryptomonnaie, ni AUCUN autre moyen de paiement.
   ⛔ Si un utilisateur demande "Acceptez-vous PayPal ?", répondre :
      "Non, nous n'acceptons pas PayPal. Les moyens de paiement disponibles sur
      L'Atelier du Terroir sont : le Wallet électronique, le Mobile Money,
      et la Carte bancaire via PayDunya."

2. DEVISE — FCFA EXCLUSIVEMENT :
   ⛔ C'EST UNE ERREUR GRAVE D'UTILISER L'EURO (€) OU LE DOLLAR ($).
   ⛔ TOUS les prix doivent être affichés UNIQUEMENT en FCFA (Franc CFA).
   ⛔ Ne JAMAIS convertir, afficher ou mentionner des prix en EUR, USD, ou toute
      autre devise. Si les données fournies par les fonctions internes indiquent
      un prix numérique, affiche-le TOUJOURS avec le suffixe "FCFA".
   ✅ Format correct : "1 500 FCFA", "25 000 FCFA"
   ⛔ Format interdit : "1.50€", "$25", "1500 EUR"

3. FORMAT OBLIGATOIRE DES CARTES (UI COMPONENTS) :
   Pour afficher des données à l'utilisateur, tu DOIS STRICTEMENT utiliser ces tags spéciaux (qui seront transformés en belles cartes interactives par l'interface) au lieu de faire des listes à puces avec des liens textuels.
   
   RÈGLES VITALES POUR LES TAGS :
   - N'utilise JAMAIS de listes à puces (ni tiret -, ni astérisque *) pour les tags.
   - N'ajoute JAMAIS de backticks (`), de guillemets ou de code blocks autour des tags.
   - N'ajoute AUCUN texte supplémentaire sur la même ligne (pas de prix initial, de remise ou de date de validité à côté). Juste le tag nu.
   - Produit : `[PRODUCT:nom_du_produit:prix:slug]` (Exemple correct : [PRODUCT:Gombo:600:gombo])
   - Commande : `[ORDER:reference:statut:montant:date]` (Exemple correct : [ORDER:ATT-1234:pending:25000:08/07/2026])
   - Wallet (Solde) : `[WALLET:solde]` (Exemple correct : [WALLET:2500])
   - Fidélité (Points) : `[LOYALTY:points:nom_du_grade]` (Exemple correct : [LOYALTY:150:Gold])
   - Profil : `[PROFILE:prenom_nom:email:role]` (Exemple correct : [PROFILE:Jean Dupont:jean@email.com:Client])

4. PÉRIMÈTRE DE RÉPONSE :
   - Ne te prononce JAMAIS sur des sujets sans rapport avec la boutique.
   - Si l'utilisateur pose une question hors sujet, réponds poliment que tu es dédié à L'Atelier du Terroir uniquement.

═══════════════════════════════════════════════════════════
RÈGLES DE COMMUNICATION
═══════════════════════════════════════════════════════════
- Réponds TOUJOURS en français, de manière chaleureuse, professionnelle et concise.
- Utilise les tags UI pour rendre l'expérience sublime (ex: [PRODUCT:Miel:5000:miel]).
- Utilise les données réelles via les fonctions disponibles pour les prix et stocks.
- Si l'utilisateur pose une question ambiguë, reformule poliment pour clarifier."""

        # Personnalisation selon l'état d'authentification
        if self.user:
            base_prompt += f"\n\nL'utilisateur connecté est {self.user.email}. " \
                           "Tu peux accéder à ses commandes, son wallet et ses points de fidélité."
        else:
            base_prompt += (
                "\n\nL'utilisateur n'est pas connecté. "
                "Tu peux l'aider à explorer les produits et catégories. "
                "Pour les commandes, le wallet ou les points de fidélité, "
                "invite-le poliment à se connecter : 'Pour consulter vos commandes, "
                "veuillez vous connecter à votre compte.'"
            )

        return base_prompt


    # ============================================================
    #  ROUTER D'EXÉCUTION DES FONCTIONS
    # ============================================================

    def _call_api(self, function_name: str, arguments: dict) -> str:
        """
        Route l'exécution vers la méthode Django interne correspondante.

        Le résultat est sérialisé en JSON pour être renvoyé au LLM,
        qui le reformulera en langage naturel.

        Args:
            function_name : Nom de la fonction (doit correspondre à API_FUNCTIONS).
            arguments     : Dictionnaire des arguments parsés depuis le tool_call.

        Returns:
            Chaîne JSON représentant le résultat de la fonction,
            ou un message d'erreur si la fonction est inconnue / l'accès refusé.
        """
        FUNCTION_ROUTER = {
            "search_products": self._api_search_products,
            "get_categories": self._api_get_categories,
            "get_active_promo_codes": self._api_get_active_promo_codes,
            "get_my_orders": self._api_get_my_orders,
            "get_wallet_balance": self._api_get_wallet_balance,
            "get_loyalty_points": self._api_get_loyalty_points,
        }

        handler = FUNCTION_ROUTER.get(function_name)

        if not handler:
            logger.warning("ChatService: fonction inconnue demandée — %s", function_name)
            return json.dumps({"error": f"Fonction '{function_name}' inconnue."})

        try:
            return handler(arguments)
        except Exception as exc:
            logger.error(
                "ChatService: erreur dans la fonction %s — %s",
                function_name,
                str(exc),
            )
            return json.dumps({"error": "Une erreur est survenue lors de la récupération des données."})

    # ============================================================
    #  FONCTIONS PUBLIQUES (sans authentification)
    # ============================================================

    def _api_search_products(self, args: dict) -> str:
        """
        Recherche des produits dans le catalogue par nom ou mots-clés.

        Exécute une requête ORM directement sur le modèle Product.
        Retourne les 5 premiers résultats les plus pertinents.

        Args:
            args: Doit contenir 'query' (str), 'category' (str, optionnel).

        Returns:
            JSON avec la liste des produits trouvés.
        """
        from apps.catalog.models import Product

        query = args.get("query", "").strip()
        category_filter = args.get("category", "").strip()

        if not query:
            return json.dumps({"error": "Le terme de recherche est vide."})

        # Construction du queryset de base
        qs = Product.objects.filter(
            is_active=True,
            name__icontains=query,
        ).select_related("category")

        # Filtre optionnel par catégorie
        if category_filter:
            qs = qs.filter(category__name__icontains=category_filter)

        # Limitation à 5 résultats pour garder la réponse concise
        products = qs[:5]

        if not products:
            return json.dumps({
                "found": 0,
                "message": f"Aucun produit trouvé pour '{query}'.",
            })

        results = [
            {
                "id": str(p.id),
                "name": p.name,
                "category": p.category.name,
                # Annotate currency explicitly so LLM never guesses
                "price_fcfa": f"{p.price} FCFA",
                "discount_price_fcfa": f"{p.discount_price} FCFA" if p.discount_price else None,
                "stock": p.stock,
                "in_stock": p.is_in_stock,
                "slug": p.slug,
                # Lien vers la page produit du frontend
                "url": f"/products/{p.slug}",
            }
            for p in products
        ]

        return json.dumps({"found": len(results), "products": results}, ensure_ascii=False)

    def _api_get_categories(self, args: dict) -> str:
        """
        Retourne la liste de toutes les catégories actives de la boutique.

        Args:
            args: Dictionnaire vide (aucun argument requis).

        Returns:
            JSON avec la liste des catégories.
        """
        from apps.catalog.models import Category

        categories = (
            Category.objects
            .filter(is_active=True, parent__isnull=True)  # Catégories racine uniquement
            .order_by("name")
        )

        results = [
            {
                "id": str(c.id),
                "name": c.name,
                "slug": c.slug,
                "url": f"/catalogue?categorie={c.slug}",
            }
            for c in categories
        ]

        return json.dumps({"categories": results}, ensure_ascii=False)

    def _api_get_active_promo_codes(self, args: dict) -> str:
        """
        Retourne la liste des codes promo actifs.
        """
        from apps.promotions.models import PromoCode
        from django.utils import timezone
        from django.db.models import Q

        now = timezone.now()
        codes = PromoCode.objects.filter(
            Q(expires_at__isnull=True) | Q(expires_at__gte=now),
            is_active=True,
            starts_at__lte=now,
        ).order_by("starts_at")

        results = []
        for c in codes:
            results.append({
                "code": c.code,
                "discount_type": c.type,
                "discount_value": str(c.value),
                "description": c.description or "",
                "valid_until": c.expires_at.strftime("%d/%m/%Y") if c.expires_at else "Illimité",
            })

        return json.dumps({"active_promo_codes": results}, ensure_ascii=False)

    # ============================================================
    #  FONCTIONS AUTHENTIFIÉES (requièrent self.user != None)
    # ============================================================

    def _check_authenticated(self) -> str | None:
        """
        Vérifie que l'utilisateur est connecté avant d'accéder à des données privées.

        Returns:
            None si l'utilisateur est authentifié.
            JSON d'erreur si l'utilisateur est anonyme.
        """
        if not self.user:
            return json.dumps({
                "error": "Vous devez être connecté pour accéder à cette information.",
                "action_required": "login",
            })
        return None

    def _api_get_my_orders(self, args: dict) -> str:
        """
        Récupère les commandes de l'utilisateur connecté.

        Filtre optionnel par statut (ex: 'delivered', 'shipped').
        Retourne les 5 dernières commandes pour rester concis.

        Args:
            args: Peut contenir 'status' (str, optionnel).

        Returns:
            JSON avec la liste des commandes.
        """
        auth_error = self._check_authenticated()
        if auth_error:
            return auth_error

        from apps.commandes.models import Order

        status_filter = args.get("status", "").strip()

        qs = Order.objects.filter(user=self.user).order_by("-created_at")

        if status_filter:
            qs = qs.filter(status=status_filter)

        # 5 dernières commandes pour rester dans la fenêtre de tokens
        orders = qs[:5]

        if not orders:
            msg = "Vous n'avez aucune commande"
            if status_filter:
                msg += f" avec le statut '{status_filter}'"
            return json.dumps({"found": 0, "message": msg + "."})

        results = [
            {
                "reference": o.reference,
                "status": o.status,
                "total_final": str(o.total_final),
                "created_at": o.created_at.strftime("%d/%m/%Y"),
                "url": f"/customer/commandes/{o.reference}",
            }
            for o in orders
        ]

        return json.dumps({"found": len(results), "orders": results}, ensure_ascii=False)

    def _api_get_wallet_balance(self, args: dict) -> str:
        """
        Récupère le solde du wallet de l'utilisateur connecté.

        Args:
            args: Dictionnaire vide (aucun argument requis).

        Returns:
            JSON avec le solde et le statut du wallet.
        """
        auth_error = self._check_authenticated()
        if auth_error:
            return auth_error

        try:
            from apps.paiements.models import Wallet
            wallet = Wallet.objects.get(user=self.user)
            return json.dumps({
                "balance": str(wallet.balance),
                "status": wallet.status,
                "url": "/customer/wallet",
            }, ensure_ascii=False)
        except Exception:
            # Si le modèle Wallet a un nom différent, on gère gracieusement l'erreur
            logger.warning("ChatService: impossible de récupérer le wallet de %s", self.user.email)
            return json.dumps({
                "error": "Impossible de récupérer le solde de votre wallet pour le moment.",
            })

    def _api_get_loyalty_points(self, args: dict) -> str:
        """
        Récupère les points de fidélité et le profil de fidélité de l'utilisateur.

        Args:
            args: Dictionnaire vide (aucun argument requis).

        Returns:
            JSON avec les points, le palier et les avantages.
        """
        auth_error = self._check_authenticated()
        if auth_error:
            return auth_error

        try:
            from apps.fidelites.models import LoyaltyProfile
            profile = LoyaltyProfile.objects.select_related("tier").get(user=self.user)
            return json.dumps({
                "points_balance": profile.points_balance,
                "tier_name": profile.tier.name if profile.tier else "Aucun",
                "url": "/customer/fidelite",
            }, ensure_ascii=False)
        except Exception:
            logger.warning(
                "ChatService: impossible de récupérer le profil fidélité de %s",
                self.user.email,
            )
            return json.dumps({
                "error": "Impossible de récupérer vos points de fidélité pour le moment.",
            })
