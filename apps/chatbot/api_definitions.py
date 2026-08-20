"""
Définitions des fonctions OpenAI (Function Calling / Tool Use).

Ce fichier centralise la description de toutes les actions que le LLM
peut décider d'exécuter pour répondre à la demande d'un utilisateur.

Chaque entrée suit le schéma OpenAI :
  {
    "name"       : identifiant snake_case de la fonction,
    "description": explication pour le LLM (doit être précise et en français),
    "parameters" : schéma JSON Schema des arguments attendus,
  }

Le router d'exécution se trouve dans ChatService._call_api() (services.py).

@module apps.chatbot.api_definitions
"""

# ============================================================
#  LISTE COMPLÈTE DES FONCTIONS DISPONIBLES POUR LE LLM
# ============================================================

API_FUNCTIONS: list[dict] = [

    # ----------------------------------------------------------
    # CATALOGUE — Endpoints publics (aucune authentification requise)
    # ----------------------------------------------------------

    {
        "name": "search_products",
        "description": (
            "Recherche des produits dans le catalogue de L'Atelier du Terroir "
            "par nom, description ou mots-clés. "
            "Utilise cette fonction quand l'utilisateur demande à voir des produits, "
            "cherche un article spécifique, ou veut connaître les disponibilités."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Terme de recherche (nom du produit, catégorie, mots-clés). Ex: 'citron', 'feuilles de moringa'.",
                },
                "category": {
                    "type": "string",
                    "description": "Filtrer par catégorie de produit. Ex: 'Fruits', 'Feuilles', 'Huile'.",
                },
            },
            "required": ["query"],
        },
    },

    {
        "name": "get_categories",
        "description": (
            "Récupère la liste de toutes les catégories de produits disponibles dans la boutique. "
            "Utilise cette fonction quand l'utilisateur demande quelles catégories existent, "
            "ou veut parcourir les rayons de la boutique."
        ),
        "parameters": {
            "type": "object",
            "properties": {},
        },
    },

    # ----------------------------------------------------------
    # COMMANDES — Endpoints authentifiés
    # ----------------------------------------------------------

    {
        "name": "get_my_orders",
        "description": (
            "Récupère les commandes de l'utilisateur connecté. "
            "Utilise cette fonction quand l'utilisateur demande à voir ses commandes, "
            "connaître le statut d'une livraison, ou vérifier son historique d'achats. "
            "Nécessite que l'utilisateur soit connecté."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "description": (
                        "Filtrer les commandes par statut. "
                        "Valeurs possibles : 'pending_payment', 'paid', 'confirmed', "
                        "'processing', 'shipped', 'delivered', 'cancelled', 'refunded'."
                    ),
                },
            },
        },
    },

    # ----------------------------------------------------------
    # WALLET — Endpoints authentifiés
    # ----------------------------------------------------------

    {
        "name": "get_wallet_balance",
        "description": (
            "Récupère le solde actuel du porte-monnaie électronique (wallet) de l'utilisateur. "
            "Utilise cette fonction quand l'utilisateur demande son solde, "
            "combien d'argent il a sur son compte, ou s'il peut payer avec son wallet. "
            "Nécessite que l'utilisateur soit connecté."
        ),
        "parameters": {
            "type": "object",
            "properties": {},
        },
    },

    # ----------------------------------------------------------
    # FIDÉLITÉ — Endpoints authentifiés
    # ----------------------------------------------------------

    {
        "name": "get_loyalty_points",
        "description": (
            "Récupère le nombre de points de fidélité de l'utilisateur, son palier (grade) actuel "
            "et les avantages dont il bénéficie. "
            "Utilise cette fonction quand l'utilisateur demande ses points, son grade de fidélité, "
            "ou les récompenses disponibles. "
            "Nécessite que l'utilisateur soit connecté."
        ),
        "parameters": {
            "type": "object",
            "properties": {},
        },
    },

    # ----------------------------------------------------------
    # PROMOTIONS — Endpoints publics
    # ----------------------------------------------------------

    {
        "name": "get_active_promo_codes",
        "description": (
            "Récupère la liste des codes promotionnels et réductions actuellement actifs et valides. "
            "Utilise cette fonction quand l'utilisateur demande s'il y a des promotions, des soldes "
            "ou s'il cherche un code promo."
        ),
        "parameters": {
            "type": "object",
            "properties": {},
        },
    },

    {
        "name": "search_packs",
        "description": (
            "Recherche les packs promotionnels de la boutique. Un pack regroupe plusieurs produits "
            "vendus ensemble à un prix fixe avantageux (coffret, lot, panier garni, assortiment, kit). "
            "Retourne le nom, le prix, la composition détaillée et le slug de chaque pack. "
            "Utilise cette fonction dès que l'utilisateur parle de pack, coffret, lot, panier garni, "
            "assortiment, box ou d'une offre groupée."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": (
                        "Mots-clés de recherche du pack. Laisse vide pour lister tous les packs "
                        "disponibles."
                    ),
                },
            },
        },
    },

    # ----------------------------------------------------------
    # RECETTES — Endpoints publics
    # ----------------------------------------------------------

    {
        "name": "search_recettes",
        "description": (
            "Recherche les recettes de cuisine publiées par la boutique. Chaque recette contient "
            "des ingrédients, des étapes de préparation et parfois une vidéo, et peut être rattachée "
            "à un produit ou à un pack. Utilise cette fonction dès que l'utilisateur cherche une "
            "recette, demande comment cuisiner ou préparer un plat, cherche une idée de repas, "
            "ou demande quoi faire avec un ingrédient précis."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": (
                        "Mots-clés : nom du plat, ou ingrédient recherché (ex: 'gombo', 'sauce "
                        "arachide'). Laisse vide pour lister les dernières recettes publiées."
                    ),
                },
            },
        },
    },
]
