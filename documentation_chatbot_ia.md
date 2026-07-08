# 📘 Documentation Technique — Module Chatbot IA

**Projet :** E-commerce L'Atelier du Terroir
**Date d'implémentation :** Juillet 2026
**Auteur :** Antigravity IA

Ce document décrit de manière exhaustive l'architecture, le fonctionnement et le détail de l'implémentation du module de Chatbot IA intégré au projet. Il a été rédigé pour permettre à tout développeur backend Django (et frontend Next.js) de comprendre, maintenir et faire évoluer cette fonctionnalité.

---

## 1. Architecture Générale

Le système repose sur une architecture en 3 tiers :
1. **Frontend (Next.js)** : Une interface utilisateur (`ChatBot.tsx`) qui capture les messages et les envoie au backend via une API sécurisée. Il gère la persistance de l'ID de conversation en `localStorage`.
2. **Backend (Django DRF)** : L'orchestrateur central. Il reçoit le message, construit un historique cohérent, et interagit avec OpenAI. La clé API n'est **jamais exposée** côté client.
3. **OpenAI (Modèle LLM)** : Le backend communique avec OpenAI (via la bibliothèque officielle Python). Il utilise le mécanisme d'**OpenAI Function Calling** pour permettre à l'IA d'interroger en direct la base de données de l'application (catalogue, commandes, wallet, etc.).

---

## 2. Prérequis & Configuration de l'Environnement

Le module nécessite l'installation du SDK Python d'OpenAI et la configuration de variables d'environnement.

### Variables d'environnement (`ecommerce_backend/.envs/.local/.env` ou en prod)
```env
OPENAI_API_KEY=sk-proj-XXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
OPENAI_MODEL=openai/gpt-4o-mini # (Optionnel, "openai/gpt-4o-mini" par défaut pour le rapport qualité/prix)
```

### Dépendances Python
Le package `openai` doit être installé dans l'environnement virtuel.
```bash
pip install openai
```

---

## 3. Détails de l'Implémentation Backend (Django)

L'implémentation backend a été réalisée au sein d'une application Django dédiée et isolée, nommée `chatbot`. 

**Chemin du module :** `ecommerce_backend/apps/chatbot/`

### 3.1. Modèles de Données
📁 `ecommerce_backend/apps/chatbot/models.py`

Deux modèles gèrent l'historique :
*   **`Conversation`** : Représente une session de chat. Elle est liée au modèle `User` (clé étrangère nullable). Si l'utilisateur n'est pas connecté, la conversation existe mais sans lien utilisateur.
*   **`Message`** : Représente une bulle de dialogue. Il contient un `role` (`user` ou `assistant`), un `content` (le texte), et est rattaché à une `Conversation`.
*   *Note : Les messages des utilisateurs non connectés (anonymes) ne sont pas persistés en base de données pour préserver le stockage, mais le contexte passe en mémoire vive durant la requête.*

### 3.2. Configuration des Signatures d'Outils (Function Calling)
📁 `ecommerce_backend/apps/chatbot/api_definitions.py`

Ce fichier exporte une liste `API_FUNCTIONS` de dictionnaires au format JSON Schema requis par OpenAI. Il décrit **ce que le LLM a le droit de faire** :
*   `search_products` (Public) : Recherche un produit.
*   `get_categories` (Public) : Liste les catégories.
*   `get_my_orders` (Authentifié) : Liste les commandes du client.
*   `get_wallet_balance` (Authentifié) : Affiche le solde du porte-monnaie.
*   `get_loyalty_points` (Authentifié) : Affiche les points de fidélité.

### 3.3. Logique Métier (Le Cœur du Système)
📁 `ecommerce_backend/apps/chatbot/services.py`

La classe `ChatService` orchestre toute la logique. C'est le fichier le plus important du module.
*   **`process_message()`** : Le point d'entrée principal. Il récupère la conversation, construit le prompt système, interroge OpenAI, détecte si OpenAI demande l'exécution d'une fonction interne (Function Calling), exécute cette fonction via l'ORM Django, et renvoie le résultat à OpenAI pour obtenir la formulation textuelle finale.
*   **`_build_context()`** : Assemble les messages. **Contrainte importante :** Seuls les 10 derniers messages sont envoyés au LLM (constante `CONTEXT_WINDOW_SIZE = 10`) afin de ne pas exploser le budget de tokens.
*   **`_build_system_prompt()`** : Le prompt injecté "en cachette" à l'IA. Il est dynamique : il informe le LLM si l'utilisateur est connecté et qui il est (email), ce qui permet à l'IA de personnaliser ses réponses et de refuser poliment d'accéder aux données privées si l'utilisateur est anonyme.
*   **Implémentations internes** : Les méthodes comme `_api_search_products()` font directement des requêtes ORM (ex: `Product.objects.filter(...)`) et renvoient les résultats en JSON stringifié au LLM.

### 3.4. Vues (Views) et Sérialiseurs (Serializers)
📁 `ecommerce_backend/apps/chatbot/views.py`
📁 `ecommerce_backend/apps/chatbot/serializers.py`

*   **`ChatView`** : Une vue de type `APIView`. Endpoint : `POST /api/v1/chatbot/chat/`.
*   **Authentification Hybride** : Les classes de permissions sont `[AllowAny]`. La vue tente d'authentifier la requête (via `TokenAuthentication`), mais si le jeton est invalide ou absent, la requête continue sans erreur en tant qu'utilisateur `AnonymousUser`. La restriction d'accès aux vraies données privées se fait dans `ChatService`.
*   **Erreurs OpenAI** : La vue intercepte proprement les exceptions `openai.RateLimitError` et `openai.AuthenticationError` pour renvoyer des HTTP 503 lisibles au frontend.
*   **Sérialiseurs** : Valident la présence du `message` et (optionnellement) du `conversation_id`.

### 3.5. Enregistrement de l'Application
📁 `ecommerce_backend/apps/chatbot/admin.py` : Enregistrement dans l'admin Django avec l'affichage des messages *Inline* dans les conversations (en lecture seule pour l'audit).
📁 `ecommerce_backend/apps/chatbot/urls.py` : Route interne de l'application.
📁 `ecommerce_backend/apps/chatbot/__init__.py` & `apps.py` : Boilerplate standard.

### 3.6. Fichiers Systèmes Modifiés
*   📁 `ecommerce_backend/config/settings/base.py` : Ajout de `"apps.chatbot"` dans `LOCAL_APPS` et ajout des paramètres `OPENAI_API_KEY`.
*   📁 `ecommerce_backend/config/urls.py` : Inclusion de `path("api/v1/chatbot/", include("apps.chatbot.urls"))`.

---

## 4. Détails de l'Implémentation Frontend (Next.js)

L'implémentation frontend se concentre sur l'encapsulation de l'appel HTTP et le maintien du contexte de conversation côté client.

### 4.1. Composant UI
📁 `ecommerce_frontend_kalvin/components/ai/ChatBot.tsx`
Composant (déjà en place) utilisant TailwindCSS et Framer Motion. Il délègue toute la logique de requête à la couche Service.

### 4.2. Couche Service (Logique de session)
📁 `ecommerce_frontend_kalvin/services/ai.service.ts`
*   Gère la lecture et l'écriture de `chatbot_conversation_id` dans le `localStorage`.
*   S'assure que si l'utilisateur rafraîchit la page, il envoie son `conversation_id` existant au backend pour reprendre la même discussion.
*   Expose une fonction `askCommerceAssistant` et une fonction utilitaire `resetConversation`.

### 4.3. Couche API (Réseau bas niveau)
📁 `ecommerce_frontend_kalvin/fonctions_api/ai.api.ts`
*   Fonction `sendChatMessage`.
*   Utilise l'instance Axios **`apiPrivate`**. C'est primordial car cette instance possède un intercepteur qui injecte le token JWT (ou plutôt le token DRF `Authorization: Token <key>`) de façon transparente si l'utilisateur est connecté.
*   Retourne une structure standardisée `Result<T>`.

---

## 5. Flux d'Exécution d'une Requête (Data Flow)

Voici le trajet complet d'une demande comme *"Combien ai-je sur mon compte wallet ?"* :

1. **Client** : L'utilisateur tape la question. Le fichier `ai.service.ts` récupère le `conversation_id` du `localStorage` (s'il existe).
2. **Axios** : `apiPrivate` détecte le token de connexion en mémoire, l'ajoute aux headers HTTP, et POST la requête sur `/api/v1/chatbot/chat/`.
3. **Django (View)** : `ChatView` valide la requête, identifie l'utilisateur (`request.user`) grâce au token DRF, et instancie `ChatService`.
4. **Django (Service)** : `ChatService` retrouve la conversation en base de données, sauvegarde la question de l'utilisateur en base de données (si connecté).
5. **OpenAI (Appel 1)** : `ChatService` envoie le prompt système + l'historique (max 10 msgs) + les descriptions des fonctions autorisées à OpenAI.
6. **OpenAI (Décision)** : OpenAI détecte que la demande de l'utilisateur correspond parfaitement à la fonction `get_wallet_balance`. Il ne renvoie pas de texte, mais renvoie un bloc de code `tool_calls`.
7. **Django (Exécution interne)** : `ChatService` détecte le bloc `tool_calls`. Il mappe la demande à la fonction `_api_get_wallet_balance()`. La fonction interroge la base (ex: `Wallet.objects.get(user=self.user)`) et renvoie `{"balance": "5000", "status": "active"}`.
8. **OpenAI (Appel 2)** : `ChatService` renvoie le résultat JSON à OpenAI avec le statut de l'outil exécuté.
9. **OpenAI (Réponse finale)** : OpenAI traduit le JSON en langage naturel : *"Vous avez actuellement 5000 FCFA sur votre porte-monnaie..."*
10. **Django (Finalisation)** : La réponse de l'IA est sauvegardée en base. `ChatView` retourne le JSON au client HTTP.
11. **Client** : Le message est affiché dans le `ChatBot.tsx`.

---

## 6. Guide de Maintenance et d'Extensibilité

Pour **ajouter une nouvelle capacité** à l'IA (exemple : *Vérifier si un produit spécifique est en promotion*), le développeur devra suivre ces 2 étapes uniques côté backend :

### Étape 1 : Décrire la fonction à OpenAI
Dans `apps/chatbot/api_definitions.py`, ajouter une nouvelle entrée à la liste :
```python
{
    "name": "check_product_promotion",
    "description": "Vérifie si un produit spécifique bénéficie actuellement d'une promotion.",
    "parameters": {
        "type": "object",
        "properties": {
            "product_name": { "type": "string", "description": "Le nom du produit" }
        },
        "required": ["product_name"]
    }
}
```

### Étape 2 : Implémenter la logique d'exécution
Dans `apps/chatbot/services.py` :
1. Mapper la fonction dans le routeur de `_call_api` :
```python
FUNCTION_ROUTER = {
    # ... autres fonctions
    "check_product_promotion": self._api_check_product_promotion,
}
```
2. Écrire la méthode privée qui exécute la requête ORM et retourne du JSON :
```python
def _api_check_product_promotion(self, args: dict) -> str:
    product_name = args.get("product_name")
    # Logique ORM Django ici (Product.objects.filter(...) etc.)
    return json.dumps({"is_promoted": True, "discount": "20%"})
```

Le module est conçu pour être extrêmement modulaire. Toute nouvelle fonction ajoutée à `api_definitions.py` sera automatiquement prise en compte par le modèle de langage au prochain appel.
