---
name: docker-env-setup
description: Phase 2 du Trading Journal — initialisation du dépôt, Next.js, Django, PostgreSQL, Docker Compose, variables d'environnement et vérification que les trois services communiquent. À utiliser pour le squelette et tout changement d'infrastructure.
---

# Phase 2 — Initialisation

## Avant de générer quoi que ce soit
1. **Vérifier les versions stables et compatibles** (Node LTS, Next.js, Python, Django LTS/stable, DRF, PostgreSQL, drf-spectacular, psycopg 3, pytest-django…) via sources officielles ; ne pas se fier à la mémoire.
2. Présenter versions + dépendances principales + prérequis locaux (Git, Docker Desktop/Compose, éventuellement Node/Python en local). Machine de l'utilisateur : **Windows 11** — fournir des commandes PowerShell compatibles, attention aux fins de ligne (`.gitattributes` en `LF`) et aux montages de volumes.
3. Donner les commandes exactes de création (`git init`, `create-next-app` avec TypeScript/Tailwind/App Router/`src/`, `django-admin startproject config`, `startapp` dans `apps/`).
4. Attendre la validation avant d'enchaîner.

## Contenu attendu
- `docker-compose.yml` : services `db` (postgres, volume nommé, healthcheck, **pas de port publié** hors dev), `backend` (dépend de `db` healthy, exécute migrations puis serveur dev), `frontend`. Réseau interne ; volume pour `storage/`.
- `backend/Dockerfile`, `frontend/Dockerfile` (multi-stage si utile ; utilisateur non-root).
- `backend/requirements/{base,dev,prod}.txt` ; `config/settings/{base,dev,prod}.py` lisant l'environnement (ex. `django-environ`).
- `.env.example` : `DJANGO_SETTINGS_MODULE`, `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS`, `POSTGRES_DB/USER/PASSWORD/HOST/PORT`, `CORS_ALLOWED_ORIGINS`, `CSRF_TRUSTED_ORIGINS`, `NEXT_PUBLIC_API_URL`, `STORAGE_BACKEND`, `SCREENSHOT_MAX_BYTES`, variables S3 (commentées). **Aucun vrai secret.**
- `.gitignore` (`.env`, `node_modules`, `.next`, `__pycache__`, `storage/*` sauf `.gitkeep`, `*.sqlite3`), `.gitattributes`, `README.md` d'installation.
- Endpoint de santé `GET /api/v1/health/` (vérifie la DB) et page frontend minimale qui l'appelle.
- Pas de module métier à ce stade.

## Vérification (résultats réels à montrer)
```bash
docker compose up -d --build
docker compose ps                                   # db healthy, backend & frontend up
docker compose exec backend python manage.py migrate
docker compose exec backend python manage.py check
curl http://localhost:8000/api/v1/health/            # {"status":"ok","database":"ok"}
# ouvrir http://localhost:3000 → la page affiche l'état de l'API
docker compose exec backend pytest                   # un test de santé
```
Si une commande échoue : lire les logs (`docker compose logs <service>`), diagnostiquer, corriger avant de poursuivre.

## Production (rappel, détaillé en phase 8)
HTTPS, PostgreSQL non exposé, secrets hors dépôt, settings `prod`, sauvegardes (voir `backup-restore`) ; skill global `deploy-vps` pour le serveur.
