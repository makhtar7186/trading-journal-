---
name: testing-strategy
description: Stratégie de tests du Trading Journal — pytest/pytest-django côté backend, Vitest + Testing Library côté frontend, tests d'isolation utilisateur, cas limites statistiques, uploads, et scénarios d'acceptation. À utiliser pour écrire ou revoir des tests, ou avant de clore une phase.
---

# Tests

## Backend (pytest + pytest-django)
- Fixtures : `user_a`, `user_b`, `api_client` authentifié, factories (`factory_boy`) pour Trade/Strategy/Screenshot.
- Par module : modèles & contraintes · CRUD · règles métier · filtres/tri/pagination/recherche · autorisations · transactions/erreurs.
- **Isolation (obligatoire pour chaque ressource)** : B ne peut ni lister, ni lire, ni modifier, ni supprimer les objets de A (404) ; `user` du corps ignoré.
- **Règles de statut** : OPEN sans `realized_rr` ; `>0` WIN, `<0` LOSS, `=0` BE ; statut fourni par le client ignoré/refusé ; `planned_rr <= 0` refusé ; clôture sans RR refusée.
- **Stats** : jeux de données calculés à la main, cas limites (voir `trading-domain-rules`), OPEN exclus, filtres avant agrégation, ordre stable.
- **Uploads** : voir `screenshots-storage` ; utiliser un stockage temporaire (`tmp_path`/settings de test).
- Couverture : suivre (`pytest --cov`) mais viser la pertinence, pas le chiffre.
- Lancer : `docker compose exec backend pytest -q`.

## Frontend (Vitest + Testing Library)
- Formulaires (validation Zod, erreurs serveur affichées), composants critiques (badge statut, cartes KPI « Non disponible »), états vide/chargement/erreur, filtres/navigation, galerie (ouverture, flèches, Échap), upload (progression, erreurs par fichier). Mock des appels API (MSW).
- Vérification responsive manuelle ou Playwright (mobile 375, tablette 768, desktop) ; optionnel : tests E2E du parcours principal.

## Scénarios d'acceptation (E2E, fin de MVP)
1. Connexion · 2. Création d'un trade OPEN · 3. Ajout de captures BEFORE/DURING/AFTER · 4. Clôture avec RR réalisé · 5. Statut déterminé par le backend · 6. Présence dans l'historique · 7. Stats recalculées · 8. OPEN exclus · 9. Isolation inter-utilisateurs · 10. Données et captures conservées après redémarrage et restauration.

## Discipline
Ne jamais annoncer un test comme réussi sans sa sortie. Agent `testeur` après chaque livraison ; `correcteur` uniquement après rejet.
