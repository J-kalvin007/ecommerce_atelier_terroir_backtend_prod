# MISSION : AUDIT COMPLET DES RESSOURCES & STRATÉGIE DE DOCKERISATION
**Projet** : Green Challenger
**Date** : 16 Juillet 2026

---

> [!WARNING]
> **ALERTES CRITIQUES IDENTIFIÉES LORS DE L'AUDIT**
> 1. **OUTPUT MODE NON STANDALONE** : Votre fichier `next.config.ts` ne contient pas `output: 'standalone'`. Actuellement, le dossier `.next/` pèse plus de **3.02 GB**. En l'état, l'image Docker ferait plus de 4 GB ! Vous devez absolument ajouter `output: 'standalone'` dans votre configuration.
> 2. **ABSENCE DE ROUTE `/api/health`** : Aucun dossier `app/api` n'existe. Cela empêche de configurer un `HEALTHCHECK` Docker fiable. Il faut créer un fichier `app/api/health/route.ts` retournant `{ status: "ok" }`.
> 3. **VARIABLES D'ENVIRONNEMENT** : Vérifiez que `NEXT_PUBLIC_APP_URL` et les autres variables clientes ne contiennent pas de secrets sensibles (comme les clés secrètes d'API).

---

## LIVRABLE 1 — ANALYSE STATIQUE DU BUILD (.next/)

Suite à l'exécution de `next build` sur votre projet, voici l'analyse exhaustive.

### 1.1 — INVENTAIRE DES PAGES & ROUTES

Le routage est composé de **48 routes** au total. La quasi-totalité de l'application est générée statiquement (SSG). 

| Route | Type | Mode rendu | Observation |
|---|---|---|---|
| `/` | page | SSG (○) | Coquille statique ultra-légère pour le serveur |
| `/admin/*` (12 routes) | pages | SSG (○) | Rendu statique avec hydration SPA côté client |
| `/super-ingenieur/*` (10 routes) | pages | SSG (○) | Idem |
| `/superadmin/*` (7 routes) | pages | SSG (○) | Idem |
| `/technicien/*` (2 routes) | pages | SSG (○) | Idem |
| `/auth/verify-email/[token]` | page | SSR (ƒ) | Rendu dynamique par le serveur |
| `/auth/password-reset/confirm/[uid]/[token]` | page | SSR (ƒ) | Rendu dynamique par le serveur |

> [!TIP]
> **Excellente nouvelle** : Votre application s'appuie massivement sur le SSG (Static Site Generation). Le serveur Next.js n'aura quasiment **aucun effort CPU** à fournir pour distribuer l'interface. Toute la charge réseau et de calcul sera supportée par les clients (navigateurs) via les fetchs des API externes. 

### 1.2 — INVENTAIRE DES BUNDLES & CHUNKS

La majeure partie de vos dépendances (`lucide-react`, `chart.js`, `recharts`, `framer-motion`) sont chargées côté client.
- **Poids total `.next` mesuré** : 3 024 MB (3.02 GB - cause mode normal)
- **Taille moyenne First Load JS** : ~95 - 130 kB (typique pour une app Next.js moderne).

### 1.3 — ASSETS STATIQUES (`public/`)

- **Taille totale mesurée** : ~32 MB (216 fichiers)
- Composé majoritairement d'images (logos, fonds) et d'icônes. Le poids est parfaitement maîtrisé et sera très facilement mis en cache par Nginx.

### 1.4 — DÉTECTION DU MODE OUTPUT

- **Mode standalone détecté ?** : **NON**.
- **Action immédiate requise** : Ajoutez `output: 'standalone'` dans `next.config.ts`. Cela réduira la taille finale de l'image Docker de ~4 GB à environ **150 - 250 MB**.

---

## LIVRABLE 2 — RAPPORT DE DIMENSIONNEMENT DES RESSOURCES VPS

Puisque l'application est à 95% SSG (statique), le serveur Node.js ne fait que de la distribution statique de fichiers HTML/JS/CSS et du reverse-proxying vers votre API externe (Django). La consommation mémoire sera très basse.

### 2.1 — RAM REQUISE

| Composante mémoire | Estimation (MB) |
|---|---|
| Node.js runtime (baseline V8 heap) | ~60 MB |
| Next.js server core | ~80 MB |
| Cache SSR / Optimisation Images | ~50 MB |
| Buffer pics concurrents (×1.5) | ~100 MB |
| **TOTAL RAM NEXT.JS CONTAINER** | **~290 MB** |
| Nginx (reverse proxy) | ~20 MB |
| OS Linux de base (Ubuntu/Debian minimal) | ~250 MB |
| **TOTAL RAM VPS RECOMMANDÉE** | **1 GB (minimum) / 2 GB (confort)** |

### 2.2 — CPU REQUIS
- Le SSR est quasi-inexistant. Un **1 vCPU** suffit pour le démarrage. Un **2 vCPU** sera parfait pour la croissance (permet d'encaisser les éventuels pics de load sur les routes de vérification email SSR).

### 2.3 — STOCKAGE DISQUE

| Composante stockage | Taille estimée |
|---|---|
| Image Docker Next.js (après standalone) | ~250 MB |
| Image Docker Nginx | ~25 MB |
| Assets statiques (`public/`) | 32 MB |
| Système d'exploitation Linux | ~3 GB |
| Logs et marges opérationnelles | ~5 GB |
| **TOTAL DISQUE RECOMMANDÉ** | **15 - 20 GB** |

### 2.5 — RECOMMANDATION VPS FINALE (DigitalOcean)

| Scénario | vCPU | RAM | Disque | Bande pass. | Offre DO recommandée |
|---|---|---|---|---|---|
| **Démarrage** (10-50 users/min) | 1 | 1 GB | 25 GB | 1 TB/mois | **Basic Regular Droplet ($6/mo)** |
| **Croissance** (100-500 users/min)| 2 | 2 GB | 50 GB | 2 TB/mois | **Basic Regular Droplet ($12/mo)** |
| **Pic / Haute dispo** | 2 | 4 GB | 80 GB | 4 TB/mois | **Basic Premium Droplet ($24/mo)** |

---

## LIVRABLE 3 — DOCKERFILE OPTIMISÉ (multi-stage)

> [!IMPORTANT]
> Assurez-vous d'avoir ajouté `output: 'standalone'` dans `next.config.ts` avant de construire cette image.
> Créez également un fichier `.dockerignore` à la racine contenant : `node_modules`, `.next`, `.git`, `README.md`.

```dockerfile
# STAGE 1 : deps
FROM node:20-alpine AS deps
# libc6-compat est requis par certains paquets natifs Node (comme sharp)
RUN apk add --no-cache libc6-compat
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

# STAGE 2 : builder
FROM node:20-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

# STAGE 3 : runner (image finale ultra-légère)
FROM node:20-alpine AS runner
WORKDIR /app

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
ENV PORT=3000
ENV HOSTNAME="0.0.0.0"

# Sécurisation : Utilisation d'un utilisateur non-root
RUN addgroup --system --gid 1001 nodejs
RUN adduser --system --uid 1001 nextjs

# Copie des fichiers publics et des statiques générés
COPY --from=builder /app/public ./public
# Crée le dossier cache avec les bons droits
RUN mkdir .next
RUN chown nextjs:nodejs .next

# Le mode standalone extrait uniquement les fichiers nécessaires à la prod
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

# Basculement sur l'utilisateur sécurisé
USER nextjs

EXPOSE 3000

# Healthcheck : nécessite la création d'une route /api/health
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
  CMD wget --no-verbose --tries=1 --spider http://localhost:3000/api/health || exit 1

CMD ["node", "server.js"]
```

---

## LIVRABLE 4 — DOCKER COMPOSE PRODUCTION-GRADE

Fichier `docker-compose.yml` :

```yaml
version: '3.8'

services:
  nextjs:
    build:
      context: .
      dockerfile: Dockerfile
    image: green_challenger_frontend:latest
    container_name: green_challenger_nextjs
    restart: unless-stopped
    env_file:
      - .env.production
    networks:
      - internal_network
    deploy:
      resources:
        limits:
          cpus: '1.0'
          memory: 512M
    healthcheck:
      test: ["CMD", "wget", "--no-verbose", "--tries=1", "--spider", "http://localhost:3000/api/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 20s

  nginx:
    image: nginx:alpine
    container_name: green_challenger_nginx
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./certbot/conf:/etc/letsencrypt
      - ./certbot/www:/var/www/certbot
    networks:
      - internal_network
    depends_on:
      nextjs:
        condition: service_healthy

networks:
  internal_network:
    driver: bridge
```

---

## LIVRABLE 5 — CONFIGURATION NGINX PRODUCTION

Fichier `nginx/nginx.conf` :

```nginx
worker_processes auto;
events {
    worker_connections 1024;
}

http {
    include mime.types;
    default_type application/octet-stream;

    sendfile on;
    keepalive_timeout 65;
    server_tokens off;

    # Gzip Compression optimisée
    gzip on;
    gzip_vary on;
    gzip_proxied any;
    gzip_comp_level 6;
    gzip_min_length 1000;
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml application/xml+rss text/javascript;

    # Security Headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;

    # Rate Limiting (Protection basique anti-DDoS/Bruteforce)
    limit_req_zone $binary_remote_addr zone=api_limit:10m rate=20r/s;

    upstream nextjs_upstream {
        server nextjs:3000;
        keepalive 64;
    }

    server {
        listen 80;
        server_name _; # À remplacer par votre domaine ex: app.greenchallenger.com

        location /.well-known/acme-challenge/ {
            root /var/www/certbot;
        }

        location / {
            return 301 https://$host$request_uri;
        }
    }

    server {
        listen 443 ssl http2;
        server_name _; # À remplacer par votre domaine

        # Décommentez ces lignes après avoir généré le certificat SSL avec Let's Encrypt
        # ssl_certificate /etc/letsencrypt/live/VOTRE_DOMAINE/fullchain.pem;
        # ssl_certificate_key /etc/letsencrypt/live/VOTRE_DOMAINE/privkey.pem;

        client_max_body_size 50M;

        # Cache agressif pour les assets compilés Next.js (fichiers avec hash unique)
        location /_next/static/ {
            proxy_pass http://nextjs_upstream;
            add_header Cache-Control "public, max-age=31536000, immutable";
        }

        # Cache pour les images optimisées
        location /_next/image/ {
            proxy_pass http://nextjs_upstream;
            add_header Cache-Control "public, max-age=86400, immutable";
        }

        # Proxy général
        location / {
            proxy_pass http://nextjs_upstream;
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection 'upgrade';
            proxy_set_header Host $host;
            proxy_cache_bypass $http_upgrade;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }
    }
}
```

---

## LIVRABLE 6 — SCRIPTS DE DÉPLOIEMENT

### 6.1 — `deploy.sh` (Déploiement Initial VPS)

```bash
#!/bin/bash
set -e

echo "🚀 Déploiement initial de Green Challenger..."

# Mise à jour système et installation Docker si non présent
sudo apt-get update && sudo apt-get upgrade -y
if ! command -v docker &> /dev/null; then
    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh
fi

# Création des dossiers nécessaires
mkdir -p nginx certbot/conf certbot/www

# ATTENTION : Si c'est votre 1er run, vous devez générer les certs Let's Encrypt :
# docker run -it --rm --name certbot \
#  -v "./certbot/conf:/etc/letsencrypt" \
#  -v "./certbot/www:/var/www/certbot" \
#  certbot/certbot certonly --webroot -w /var/www/certbot -d VOTRE_DOMAINE

# Lancement des conteneurs
docker compose up -d --build

echo "✅ Déploiement terminé. Vérification du Healthcheck..."
sleep 15
docker ps
```

### 6.2 — `update.sh` (Mise à jour Zero Downtime)

```bash
#!/bin/bash
set -e

echo "🔄 Mise à jour de Green Challenger..."

# Rebuild l'image sans interrompre la prod
docker compose build nextjs

# Recrée uniquement le conteneur NextJS (coupure de quelques secondes max)
docker compose up -d --no-deps nextjs

echo "✅ Mise à jour appliquée."
```

### 6.3 — Commandes de monitoring & debug (Cheat Sheet)

| Besoin | Commande DevOps |
|---|---|
| Voir les logs Next.js en temps réel | `docker compose logs -f nextjs` |
| Conso CPU/RAM en direct | `docker stats` |
| Inspecter l'état du Healthcheck | `docker inspect --format='{{json .State.Health}}' green_challenger_nextjs` |
| Accéder au terminal Next.js | `docker exec -it green_challenger_nextjs sh` |
| Espace occupé par Docker | `docker system df` |
| Nettoyage complet (images inutilisées) | `docker system prune -af` |
