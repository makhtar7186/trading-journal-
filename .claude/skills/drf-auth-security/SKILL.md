---
name: drf-auth-security
description: Authentification par session/cookies HTTP-only + CSRF, isolation utilisateur et durcissement Django/DRF/Next.js pour le Trading Journal. À utiliser pour login/logout, permissions, CORS, settings de production et revue de sécurité.
---

# Auth & sécurité

## Authentification
- Endpoints : `POST /api/v1/auth/login/`, `POST /api/v1/auth/logout/`, `GET /api/v1/auth/me/` (+ `refresh` seulement si on choisit des jetons).
- **Recommandation par défaut** : sessions Django (cookie `HttpOnly`, `Secure` en prod, `SameSite=Lax`) + CSRF. Plus simple et plus sûr que des JWT en `localStorage`. Si le front et l'API sont sur des origines différentes, documenter `SameSite`, `CSRF_TRUSTED_ORIGINS`, `CORS_ALLOWED_ORIGINS` et `CORS_ALLOW_CREDENTIALS`. Préférer un même domaine via reverse proxy / rewrites Next.js.
- Endpoint pour obtenir le cookie CSRF (`ensure_csrf_cookie`) ; le front envoie `X-CSRFToken` sur toute requête non sûre.
- Pas d'inscription publique : compte créé via `createsuperuser` / commande de management.
- Limiter les tentatives de login (throttling DRF `ScopedRateThrottle` ou `django-axes` si justifié).
- Documenter le fonctionnement des sessions dans `docs/api.md`.

## Autorisation
- `DEFAULT_PERMISSION_CLASSES = [IsAuthenticated]` globalement ; ouvrir explicitement les exceptions.
- Isolation par propriétaire dans **chaque** queryset (voir `django-module`). Ne jamais lire `user_id` du corps de la requête.
- Tests obligatoires d'isolation (A ne voit/modifie/supprime rien de B), y compris captures et stratégies.

## Durcissement
- Secrets via variables d'environnement (`SECRET_KEY`, DB, S3) ; jamais dans le dépôt. `.env` dans `.gitignore`, `.env.example` à jour.
- `DEBUG=False` en prod ; `ALLOWED_HOSTS` explicites ; `SECURE_SSL_REDIRECT`, `SECURE_HSTS_*`, `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, `X_FRAME_OPTIONS`, `SECURE_CONTENT_TYPE_NOSNIFF`.
- Settings séparés : `config/settings/{base,dev,prod}.py`.
- PostgreSQL non publié sur l'hôte en prod (réseau Docker interne uniquement).
- Handler d'exceptions central ; logs sans secrets, sans données sensibles inutiles ; ne pas renvoyer de traces en prod.
- Dépendances épinglées (`requirements/`), mises à jour documentées.
- Uploads : voir `screenshots-storage`.

Avant une mise en ligne : lancer le skill global `security-review`.
