<div align="center">
  <img src="https://img.icons8.com/color/96/000000/django.png" alt="Django" width="80" height="80"/>
  <h1>L'Atelier du Terroir — Backend Architecture & Core API</h1>
  <p><strong>Le Moteur E-Commerce Haute Performance • Conception Modulaire • Intelligence Artificielle</strong></p>

  [![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
  [![Django](https://img.shields.io/badge/Django-4.2+-092E20?style=for-the-badge&logo=django&logoColor=white)](https://djangoproject.com)
  [![Django REST Framework](https://img.shields.io/badge/DRF-API-red?style=for-the-badge&logo=django)](https://www.django-rest-framework.org/)
  [![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Database-316192?style=for-the-badge&logo=postgresql&logoColor=white)](https://postgresql.org)
  [![Supabase](https://img.shields.io/badge/Supabase-S3_Storage-3ECF8E?style=for-the-badge&logo=supabase&logoColor=white)](https://supabase.com)
  [![OpenAI](https://img.shields.io/badge/OpenAI-Function_Calling-412991?style=for-the-badge&logo=openai&logoColor=white)](https://openai.com)
  [![PayDunya](https://img.shields.io/badge/PayDunya-Gateway-blue?style=for-the-badge)](https://paydunya.com)
</div>

<br>

Ce document constitue la **référence architecturale absolue et exhaustive** du backend Django de la plateforme e-commerce "L'Atelier du Terroir". 
Rédigée avec une rigueur d'ingénierie stricte, cette documentation est destinée aux ingénieurs DevOps, architectes logiciels, et développeurs backend seniors. Elle détaille l'intégralité des flux de données, des règles métiers complexes (Paiements IPN, Snapshotting de commandes, Verrouillages de bases de données), des intégrations tierces et des choix architecturaux structurant cette application Headless de classe entreprise.

---

## 🏛️ 1. Architecture Système et Flux de Données Globaux

Le système repose sur une architecture orientée services (SOA) monolithe-modulaire stricte. Le backend agit exclusivement comme une API RESTful (Headless E-commerce), orchestrant les données entre le frontend Next.js et divers services externes hautement spécialisés.

```mermaid
graph TD
    %% Couleurs et Styles Premium
    classDef client fill:#f9fafb,stroke:#d1d5db,stroke-width:2px,color:#111827;
    classDef backend fill:#111827,stroke:#3b82f6,stroke-width:2px,color:#ffffff;
    classDef database fill:#047857,stroke:#064e3b,stroke-width:2px,color:#ffffff;
    classDef external fill:#6366f1,stroke:#4338ca,stroke-width:2px,color:#ffffff;
    
    %% Nœuds
    Client[📱 Frontend \n Next.js / Zustand / Axios]:::client
    
    subgraph "🚀 Serveur Django DRF (Backend E-commerce)"
        API[⚡ Routeur API & \n Token Auth]:::backend
        
        subgraph "📦 Modules Métiers Isolés (Apps)"
            Catalog[🛍️ Catalogue & Stocks]:::backend
            Orders[🛒 Commandes & Paniers]:::backend
            Pay[💳 Paiements & Wallets]:::backend
            Loyalty[⭐ Fidélités]:::backend
            Promo[🎁 Promotions]:::backend
            Delivery[🚚 Livraisons]:::backend
            Chatbot[🤖 Agent IA]:::backend
        end
        
        API --> Catalog & Orders & Pay & Loyalty & Promo & Delivery & Chatbot
    end
    
    DB[(🗄️ PostgreSQL \n Données Transactionnelles)]:::database
    S3[☁️ Supabase S3 \n Stockage Médias Distant]:::external
    LLM[🧠 OpenAI API \n Function Calling]:::external
    Mail[📧 Brevo / Anymail \n Emails Transactionnels]:::external
    Gateway[🏦 PayDunya \n Passerelle & IPN]:::external
    
    %% Relations
    Client -- "HTTPS / JSON REST" --> API
    
    Catalog & Orders & Pay & Loyalty & Promo & Delivery & Chatbot --> DB
    Catalog --> S3
    Chatbot <--"Inférence & Outils"--> LLM
    Orders & Pay --> Mail
    Pay <--"Webhooks (IPN) Asynchrones"--> Gateway
```

---

## 📂 2. Arborescence Complète et Cartographie des Fichiers

Le projet suit le standard industriel **Cookiecutter Django**, garantissant une séparation stricte entre la configuration (settings), la logique applicative (apps) et l'environnement d'exécution. L'arborescence ci-dessous détaille le rôle de chaque composant critique.

```text
ecommerce_backend/
├── ⚙️ config/                           # Configuration globale du projet Django
│   ├── settings/                        # Settings séparés par environnement (12 Factor App)
│   │   ├── base.py                      # Socle commun (Middlewares, INSTALLED_APPS, clés API)
│   │   ├── local.py                     # Config de développement (Debug=True, django-debug-toolbar)
│   │   └── production.py                # Config prod (Sentry, S3, WhiteNoise, Security headers)
│   ├── urls.py                          # Routeur principal (Inclusion de tous les endpoints /api/v1/*)
│   ├── wsgi.py                          # Interface serveur synchrone (Gunicorn/uWSGI)
│   └── asgi.py                          # Interface serveur asynchrone (Daphne/Uvicorn)
│
├── 💼 apps/                             # Applications Métier (Logique encapsulée & découplée)
│   │
│   ├── core/                            # Socle technique fondamental
│   │   ├── models.py                    # Classe BaseModel (UUID natif, dates auto, structure générique)
│   │   └── permissions.py               # Contrats DRF (IsPlatformAdmin, IsCustomer, IsOwnerOrReadOnly)
│   │
│   ├── catalog/                         # Gestion PIM (Product Information Management)
│   │   ├── models.py                    # Product, Category, ProductVariant, ProductImage
│   │   ├── signals.py                   # /!\ CRITIQUE : Synchronisation bidirectionnelle des stocks
│   │   ├── serializers.py               # Sérialisation complexe avec nested relations
│   │   └── views.py                     # Vues publiques (catalogue) et sécurisées (admin)
│   │
│   ├── commandes/                       # Order Management System (OMS)
│   │   ├── models.py                    # Cart, Order, OrderItem (Snapshot prix/nom immuable)
│   │   └── services.py                  # Logique de transformation Panier -> Commande
│   │
│   ├── paiements/                       # Moteur de transactions financières et Wallet
│   │   ├── models.py                    # Wallet, WalletTransaction, Payment (Tracking gateway)
│   │   ├── services.py                  # Transactions atomiques, select_for_update, Idempotence
│   │   ├── gateways/                    # Intégration API externes
│   │   │   └── paydunya.py              # Client API PayDunya (Token generation, Verify)
│   │   └── views.py                     # /!\ Endpoint IPN PayDunya (Webhooks)
│   │
│   ├── fidelites/                       # Moteur de fidélisation et récompenses
│   │   └── models.py                    # LoyaltyProfile (Solde points), LoyaltyTier (Paliers Or/Argent)
│   │
│   ├── livraisons/                      # Logistique et tarification
│   │   └── models.py                    # ShippingMethod, DeliveryAddress (Calculs de frais)
│   │
│   ├── promotions/                      # Moteur de règles de réduction conditionnelles
│   │   └── models.py                    # CouponCode, Discount (Conditions d'éligibilité)
│   │
│   └── chatbot/                         # Agent IA Intelligent (RAG & Function Calling)
│       ├── models.py                    # Conversation, Message (Traçabilité des échanges)
│       ├── services.py                  # Orchestration OpenAI, fenêtrage de contexte (10 msgs max)
│       └── api_definitions.py           # Définition JSON Schema des outils (outils exposés à l'IA)
│
├── 👤 ecommerce_backend/users/          # Gestion des Identités et Authentification
│   ├── models.py                        # Modèle User customisé (email en primary identifier, rôles)
│   └── adapters.py                      # Adaptation des flux d'inscription allauth (dj-rest-auth)
│
├── 📦 requirements/                     # Dépendances Python (base.txt, local.txt, production.txt)
├── 🛠️ manage.py                         # CLI Django pour l'administration et les migrations
└── 🔐 .envs/.local/.env                 # Variables d'environnement secrètes (GitIgnored)
```

---

## 🔍 3. Plongée au Cœur des Modules (Deep-Dive Technologique)

Ce système e-commerce ne se contente pas de stocker des données, il implémente des règles métiers strictes de niveau bancaire et des sécurités contre les anomalies de concurrence (Race Conditions).

### 3.1. `apps.core` : La Fondation Architecturale
Ce module garantit l'homogénéité du code et la sécurité des accès.
- **`BaseModel`** : Chaque entité de la base de données n'utilise **pas d'ID auto-incrémenté**. Tous les modèles héritent de `BaseModel` qui injecte un **UUID version 4** comme clé primaire. Cela prévient l'énumération des ressources (Insecure Direct Object Reference) par un attaquant et facilite les fusions de bases de données. Le modèle gère aussi automatiquement les horodatages `created_at` et `updated_at`.
- **`permissions.py`** : Définit les contrats d'accès DRF personnalisés. La classe `IsOwnerOrReadOnly` garantit de manière cryptographique qu'un utilisateur ne peut modifier que ses propres ressources (son profil, son panier, ses adresses).

### 3.2. `apps.catalog` : Moteur de Catalogue et Intégrité des Stocks
La gestion de catalogue (PIM) doit être rapide et cohérente.
- **Modélisation Hiérarchique** : Un produit (`Product`) est rattaché à une `Category` (qui peut avoir des sous-catégories) et possède de multiples images (`ProductImage`). Les spécificités de poids ou de taille sont gérées via les `ProductVariant`.
- **Signaux de Synchronisation (`signals.py`)** : C'est le cœur réactif du catalogue. Lors de la création d'un produit, un signal génère automatiquement une variante par défaut. Lors d'un achat, les signaux utilisent la méthode `update()` directement sur l'ORM (ex: `Product.objects.filter(pk=id).update(stock=F('stock') - quantity)`) au lieu de `save()`, empêchant ainsi les *race conditions* si deux clients achètent le même produit à la même milliseconde.

### 3.3. `apps.commandes` : Immutabilité Historique (Snapshotting)
Un système e-commerce légalement conforme ne doit jamais altérer les factures passées.
- **Le Panier (`Cart` & `CartItem`)** : Entité mutable en relation 1-to-1 avec l'utilisateur. Le panier calcule en temps réel les totaux.
- **La Commande (`Order` & `OrderItem`)** : Le cœur du système. Lors de la conversion d'un panier en commande, le système opère un "Snapshot". Les objets `OrderItem` ne pointent pas seulement vers l'ID du produit ; ils **copient en dur** le `product_name` et le `unit_price` exacts à la milliseconde de l'achat. Ainsi, si un administrateur change le prix du produit le lendemain ou le supprime, l'historique financier de la commande reste parfaitement intact.

### 3.4. `apps.paiements` : Moteur Financier, Wallets et Webhooks IPN
Ce module est le plus sensible du projet. Il gère les flux monétaires réels et virtuels.

#### 🏦 La Passerelle PayDunya (`gateways/paydunya.py`)
- L'intégration de PayDunya ne se fait pas via le frontend. C'est le backend Django qui initie la transaction (S2S - Server to Server) et génère un token de paiement sécurisé.
- La classe `PayDunyaGateway` centralise la cryptographie et l'authentification avec l'API PayDunya (clés Master, Private, Token).

#### 💸 Le Portefeuille Interne (Wallet)
- Les utilisateurs disposent d'un compte prépayé interne (`Wallet`).
- Les transactions (`WalletTransaction`) gardent une trace inaltérable des crédits et débits.
- **Verrouillage Pessimiste** : Pour éviter qu'un utilisateur dépense deux fois son solde en exécutant deux requêtes simultanées, la méthode `WalletService.debit()` utilise `select_for_update()`. La ligne de la base de données (PostgreSQL) est physiquement verrouillée jusqu'à la fin de la transaction atomique (`@transaction.atomic`).

#### 🔄 Gestion des Webhooks (IPN - Instant Payment Notification)
- Lorsque PayDunya valide un paiement, il envoie un Webhook (POST asynchrone) sur l'endpoint `/api/v1/paiements/ipn/`.
- **Idempotence** : Le `PaymentService` est conçu pour être idempotent. Si PayDunya envoie le même webhook 3 fois (en cas de retry réseau), le système vérifie le `webhook_token`. Si la transaction est déjà marquée `SUCCESS`, la requête est acquittée sans re-créditer l'utilisateur, empêchant toute création monétaire frauduleuse.

### 3.5. `apps.chatbot` : L'Agent Intelligence Artificielle (RAG & Tool Calling)
Ce module transforme l'API en une interface conversationnelle intelligente, dotée d'une mémoire et de "mains" pour agir sur le système.

- **Persistance et Mémoire** : Les conversations sont stockées via les modèles `Conversation` et `Message`. L'historique permet à l'IA de comprendre le contexte.
- **Contexte Coulissant (`ChatService`)** : Le service extrait uniquement les **10 derniers messages** d'une `Conversation`. Cela préserve le contexte (ex: "Et le deuxième produit dont tu parlais ?") tout en évitant d'exploser la limite de tokens d'OpenAI et de générer des factures astronomiques.
- **OpenAI Function Calling (`api_definitions.py`)** : Le modèle LLM (openai/gpt-4o-mini) ne se contente pas de générer du texte. Il reçoit en pré-prompt le schéma technique de l'application via des spécifications JSON Schema.
- **Flux d'exécution IA** : 
  1. L'utilisateur demande : *"Combien ai-je sur mon compte Wallet ?"*.
  2. L'IA analyse et répond (en JSON caché) : *"Je dois exécuter la fonction `get_wallet_balance()`"*.
  3. Le serveur Django intercepte cette demande, exécute la fonction Python, lit la base PostgreSQL, et renvoie le résultat JSON à l'IA (`{"balance": 15000}`).
  4. L'IA rédige alors une phrase naturelle et contextualisée : *"Bonjour ! Votre portefeuille contient actuellement 15 000 FCFA."*

---

## 🔌 4. Intégrations Tierces, Stockage et Notifications

Le backend délègue les tâches lourdes ou non-relationnelles à des services SaaS spécialisés.

### ☁️ Supabase S3 (Stockage des Médias Découplé)
Pour garantir l'élasticité des serveurs et éviter de perdre les données lors d'un redéploiement Docker, **aucun fichier média n'est stocké sur le serveur local**.
- **Configuration (`production.py`)** : Le système utilise le package `django-storages` avec le backend `boto3`.
- **Protocole** : Les fichiers uploadés depuis l'admin Django sont directement envoyés au service de stockage de Supabase via l'API compatible AWS S3.
- **Variables liées** : `DJANGO_AWS_ACCESS_KEY_ID`, `DJANGO_AWS_S3_ENDPOINT_URL`.

### 📧 Brevo / Anymail (Moteur d'E-mails Transactionnels)
La délivrabilité des emails est critique (confirmations de commandes, réinitialisation de mots de passe).
- L'infrastructure n'utilise pas le SMTP classique, souvent bloqué ou marqué en spam.
- **Configuration** : `anymail.backends.brevo.EmailBackend` injecte les emails directement via l'API HTTP de Brevo.
- Le traitement est conçu pour être asynchrone (via Celery ou threads dédiés) afin de ne pas ralentir le cycle de réponse HTTP au frontend.

### 🛡️ Authentification (dj-rest-auth & DRF Tokens)
- Le système ne gère pas de sessions basées sur les cookies classiques.
- Il utilise une approche Stateless : L'authentification repose sur des **Tokens DRF**.
- Lors du login, le frontend reçoit un Token qu'il chiffre et stocke. À chaque requête privée, le frontend injecte le header `Authorization: Token <clé_token>`.

---

## ⚙️ 5. Guide de Déploiement et d'Exploitation (Production)

L'architecture est prête pour le déploiement Cloud-Native (Docker, Kubernetes, ou PaaS comme Render/Railway).

### Variables d'Environnement Obligatoires (Production)
Le déploiement échouera si ces variables ne sont pas correctement injectées dans l'environnement du conteneur.

```env
# ==========================================
# 1. CŒUR SYSTÈME ET SÉCURITÉ
# ==========================================
DJANGO_SECRET_KEY="<clé_complexe_64_caractères_aléatoires>"
DJANGO_ALLOWED_HOSTS="api.atelierduterroir.com,ecommerce-atelier-terroir-backtend-prod.onrender.com"
DJANGO_CORS_ALLOWED_ORIGINS="https://atelierterroirsolime.vercel.app"
DJANGO_SECURE_SSL_REDIRECT="True"

# ==========================================
# 2. BASES DE DONNÉES (POSTGRESQL)
# ==========================================
DATABASE_URL="postgres://user:password@hostname:5432/dbname"
CONN_MAX_AGE=60  # Maintien des connexions persistantes pour les perfs

# ==========================================
# 3. STOCKAGE MÉDIAS DISTANT (SUPABASE S3)
# ==========================================
DJANGO_AWS_ACCESS_KEY_ID="<supabase_access_key>"
DJANGO_AWS_SECRET_ACCESS_KEY="<supabase_secret_key>"
DJANGO_AWS_STORAGE_BUCKET_NAME="<nom_du_bucket>"
DJANGO_AWS_REGION_NAME="eu-central-1"
DJANGO_AWS_S3_ENDPOINT_URL="https://<project_id>.supabase.co/storage/v1/s3"

# ==========================================
# 4. PASSERELLE DE PAIEMENT (PAYDUNYA)
# ==========================================
PAYDUNYA_MASTER_KEY="<cle_master>"
PAYDUNYA_PRIVATE_KEY="<cle_privee>"
PAYDUNYA_TOKEN="<token>"
PAYDUNYA_MODE="live"  # 'test' ou 'live'

# ==========================================
# 5. EMAILS TRANSACTIONNELS (BREVO)
# ==========================================
BREVO_API_KEY="xkeysib-<ta_cle_api_brevo>"
DJANGO_DEFAULT_FROM_EMAIL="Atelier du Terroir <contact@atelierduterroir.com>"

# ==========================================
# 6. INTELLIGENCE ARTIFICIELLE (OPENAI)
# ==========================================
OPENAI_API_KEY="sk-proj-<ta_cle_api_openai>"
OPENAI_MODEL="openai/gpt-4o-mini"
```

### Séquence Stricte de Déploiement CI/CD
Lors de toute mise à jour du code source en production, les commandes suivantes doivent être exécutées séquentiellement (généralement automatisées via un pipeline GitHub Actions ou Render) :

```bash
# 1. Installation des dépendances verrouillées
pip install -r requirements/production.txt

# 2. Vérification de l'intégrité du système
python manage.py check --deploy

# 3. Application des migrations de bases de données (Modification du schéma)
python manage.py migrate --noinput

# 4. Compilation et collecte des fichiers statiques pour le CDN (WhiteNoise)
python manage.py collectstatic --noinput

# 5. Redémarrage du worker WSGI (Gunicorn)
# (Géré automatiquement par Docker/Render)
```

---

## 🛠️ 6. Guide de Maintenance et Philosophie d'Évolutivité

Ce projet a été conçu selon le principe SOLID et la Clean Architecture. Il est hautement modulaire.

### 📝 Cas Pratique : Comment ajouter un nouveau module métier ?
Si le business décide de créer un module d'enchères, vous ne devez pas polluer le code existant :
1. Créez un dossier isolé `apps/encheres/`.
2. Définissez les modèles dans `models.py` (héritant toujours de `apps.core.models.BaseModel`).
3. Créez des `serializers.py` pour valider les flux JSON entrants.
4. Déclarez les routes dans `urls.py` et incluez ce fichier dans `config/urls.py` sous le scope `/api/v1/`.
5. Enregistrez l'application en ajoutant `"apps.encheres"` dans la liste `LOCAL_APPS` du fichier `config/settings/base.py`.
6. Générez les migrations : `python manage.py makemigrations encheres`.

### 🤖 Cas Pratique : Comment doter l'IA de nouvelles compétences ?
L'agent IA est pensé comme une plateforme. Pour lui apprendre à "Vérifier le statut d'un code promotionnel", l'intervention est minime :
1. **Spécification (Le Cerveau)** : Dans `apps/chatbot/api_definitions.py`, ajoutez la définition JSON Schema stricte de la fonction (paramètres requis, types).
2. **Câblage (Le Système Nerveux)** : Dans `apps/chatbot/services.py`, ajoutez le nom de la fonction dans le dictionnaire `FUNCTION_ROUTER` de la méthode `_call_api()`.
3. **Exécution (Les Muscles)** : Créez la fonction Python correspondante dans `services.py`. Cette fonction doit lire la base de données Django et retourner une chaîne JSON (ex: `{"is_valid": True, "discount_percentage": 15}`). L'IA lira ce JSON et formulera une réponse polie au client. Le tout se fait de manière transparente pour le frontend.

---
<div align="center">
  <p><i>Code source conçu pour l'excellence, optimisé pour la performance sous haute charge, et architecturé pour traverser les années.</i></p>
  <p><b>Documentation Technique — Propriété de L'Atelier du Terroir © 2026</b></p>
</div>
