---
name: nextjs-feature
description: Recette pour créer une fonctionnalité frontend Next.js (App Router) du Trading Journal — structure features/, client API typé, formulaires React Hook Form + Zod, états chargement/vide/erreur, tests. À utiliser pour toute page ou feature frontend.
---

# Feature frontend Next.js

## Organisation
```
src/app/(dashboard)/<route>/page.tsx   # fine : compose la feature
src/features/<feature>/
  components/   hooks/   api.ts   schemas.ts   types.ts   index.ts
src/services/api-client.ts             # fetch wrapper : credentials, CSRF, erreurs normalisées
src/components/ui/                     # shadcn/ui
src/components/shared|layout/
src/schemas/  src/types/  src/lib/
```
Ne pas créer de dossier vide ; regrouper par feature, pas par type technique global.

## Règles
- TypeScript **strict**, pas de `any` ; types API alignés sur le schéma OpenAPI (génération possible avec `openapi-typescript` si pertinent).
- Server Components par défaut ; `"use client"` seulement pour interactivité (formulaires, graphiques, galerie).
- Client API unique (`services/api-client.ts`) : appelle `/api/v1/...` en **same-origin** (proxy `rewrites` Next → Django, slash final conservé), `credentials: "include"`, `cache: "no-store"`, en-tête `X-CSRFToken` sur méthodes non sûres (cookie récupéré via `/auth/csrf/` au besoin), erreurs normalisées `ApiError {status, message, fieldErrors}`. Redirection vers login sur 401/403 via `AuthProvider`.
- État des listes (filtres, tri, page) dans l'URL (`useSearchParams` + `router.replace`), composant enveloppé dans `<Suspense>`. Pas de `setState` dans un `useEffect` (règle ESLint react-hooks) : dériver l'état ou utiliser un « brouillon » comparé à la source.
- Données en TanStack Query (clés `["trades", ...]`, invalidation après mutation). Décimaux en chaîne de bout en bout.
- Données serveur : fetch côté serveur ou TanStack Query si cache/mutations le justifient (ne l'ajouter que si utile).
- **Formulaires** : React Hook Form + `zodResolver`. Le schéma Zod reflète les règles (RR prévu > 0, RR réalisé requis à la clôture) mais **le backend reste juge** : afficher les `fieldErrors` serveur sur les champs. Ne jamais envoyer de `status` de clôture ni de `user`.
- Dates : envoyer en ISO avec fuseau ; afficher selon le fuseau des réglages.
- Chaque vue gère : **chargement** (skeleton), **vide** (message utile + action), **erreur** (message + réessayer).
- Suppression : dialogue de confirmation. Succès/échec : toasts.
- Listes : filtres/tri/pagination pilotés par l'URL (query params), recherche avec debounce.
- Accessibilité : labels liés, focus visible, navigation clavier, `aria-live` pour toasts/erreurs, contrastes AA.

## Tests (Vitest/Jest + Testing Library)
Validation du formulaire · affichage des erreurs serveur · états vide/chargement/erreur · filtres/navigation · interactions de galerie. Voir `testing-strategy`.

## Associer
`ui-dark-theme` pour le visuel ; skill global `frontend-expert` pour l'architecture ; agents `coder-frontend` + `testeur`.
