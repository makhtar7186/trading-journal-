# CLAUDE.md — Trading Journal

Application web personnelle de journal de trading (saisie manuelle). Source de vérité fonctionnelle : [Trading_projet.md](Trading_projet.md). En cas de conflit, ce dossier de conception prime ; en cas d'ambiguïté structurante, poser une question avant de décider.

## État du projet

- Phase 1 (conception) et Phase 2 (squelette Docker, 3 services vérifiés) : validées.
- **Phase 3 (backend) : implémentée, en attente de validation** — User UUID personnalisé (`accounts.User`, champ `timezone`), auth par session + CSRF, API `trades` et `strategies`, 72 tests pytest. Reste hors phase : captures (5), analytics (6).
- **Phase 4 (frontend) : implémentée, en attente de validation** — connexion, dashboard (comptages + derniers trades seulement), journal (filtres/tri/pagination dans l'URL), fiche, création/édition/clôture/réouverture/suppression, stratégies, paramètres (fuseau). Analytics et calendrier sont des pages « pas encore disponible » (pas de fausses données). 85 tests Vitest.
- **Phase 5 (captures) : implémentée, en attente de validation** — stockage abstrait (`core/storage` : local + S3 via boto3), `apps/screenshots` (upload multi-fichiers tout-ou-rien, ré-encodage Pillow qui supprime l'EXIF, accès privé authentifié, nettoyage des fichiers à la suppression y compris en cascade), galerie + visionneuse + upload avec progression côté frontend. 122 tests backend, 112 frontend. **S3 testé uniquement avec moto (simulé), pas contre un vrai bucket.**
- **Phase 6 (analytics) : implémentée, en attente de validation** — `apps/analytics` (calculs purs `stats.py` en Decimal, `selectors.py`, 7 endpoints `/analytics/{overview,performance,equity-curve,by-asset,by-market,by-strategy,by-period}/`), dashboard et page Analytics avec Recharts. 185 tests backend, 166 frontend. Décision : **les filtres de période s'appliquent à la date de clôture** (jours dans le fuseau de l'utilisateur) ; les trades OPEN sont exclus (seul `open_trades` les compte, hors filtre de période). Le serveur renvoie `null` pour tout indicateur non défini (jamais 0 ni infini). **Les graphiques n'ont pas pu être vérifiés visuellement par capture** (structure DOM vérifiée seulement).
- **Phase 7 (calendrier et finitions) : implémentée, en attente de validation** — `GET /analytics/calendar/?month=YYYY-MM` + page Calendrier (grille ARIA « grid » navigable au clavier, détail du jour, filtres marché/stratégie, URL partageable) ; `error.tsx`, `global-error.tsx`, `not-found.tsx` ; session expirée détectée globalement (retour à /login avec message) ; lien d'évitement, cibles tactiles ≥ 44 px, audit automatisé axe-core de 13 vues. 216 tests backend, 257 frontend. Décisions : un trade clôturé figure à sa **date de clôture**, un trade **ouvert à sa date de prise** (sans résultat) ; **semaine du lundi**.
- **Phase 8 (version Windows executable + finitions) : implementee et validee par l'utilisateur** - deploiement VPS remplace, a la demande de l'utilisateur, par un executable Windows (`desktop/`, voir `docs/desktop.md`) : au 1er lancement, detection de PostgreSQL, sinon installation officielle EDB (hash + Authenticode, UAC une fois) et configuration (role sans superuser), assistant de creation de compte, page Creer un compte sur `/login` (locale uniquement), sauvegardes `.tjbackup`. **Repli SQLite** si PostgreSQL n'a jamais pu etre configure (jamais si PostgreSQL fonctionnait deja), puis proposition de migration vers PostgreSQL au lancement suivant (sauvegarde, import atomique, decompte verifie, SQLite conserve). Deconnexion : `useLogout` (`queryClient.clear()` seul laissait l'ancien utilisateur dans AuthProvider et la page de connexion renvoyait au dashboard). 280 tests backend, 281 frontend, 192 desktop (dont e2e sur l'exe fige, migration reelle SQLite->PostgreSQL 17, GUI Tk hors ecran). Setup.exe compile (Inno Setup 7). **Non verifie : installation reelle de PostgreSQL via UAC sur machine vierge ; executable non signe.**
- Décisions validées en phase 3 : un trade clôturé **peut être rouvert** (`PATCH realized_rr: null` → OPEN, `closed_at` effacé) ; les **BE sont ignorés** dans les séries de gains/pertes ; `DELETE /strategies/{id}/` **désactive** (jamais de suppression) ; `status` est en lecture seule.
- Plan complet : 8 phases (voir §12 du dossier). Ne **jamais** passer à la phase suivante sans validation explicite de l'utilisateur.

## Stack (imposée)

| Couche | Choix |
|---|---|
| Frontend | Next.js (App Router), React, TypeScript strict, Tailwind, shadcn/ui, Recharts, React Hook Form, Zod |
| Backend | Python, Django, Django REST Framework, OpenAPI (drf-spectacular), pytest + pytest-django |
| Base | PostgreSQL, ORM Django, migrations versionnées, UUID partout |
| Images | Stockage local (dev) / S3 compatible (prod) derrière une interface |
| Infra | Docker Compose, `.env.example`, settings dev/prod séparés |

Vérifier les versions stables et compatibles **avant** de les figer (ne pas se fier à la mémoire). Pas de microservices : **monolithe modulaire**.

## Structure cible

```
frontend/  (src/app/(auth)|(dashboard)/…, components/, features/, services/, hooks/, schemas/, types/, lib/)
backend/   (config/settings/, apps/{accounts,trades,strategies,screenshots,analytics}, core/, tests/, requirements/)
storage/  docs/  docker-compose.yml  .env.example  README.md
```

Cible indicative : suivre les conventions réelles de Next.js/Django, ne pas créer de dossiers vides ni d'abstractions prématurées.

## Règles métier non négociables

- **Le backend est la source de vérité** des statuts et des statistiques. Le frontend n'envoie jamais le statut de clôture.
- Statut dérivé de `realized_rr` : `>0` WIN, `<0` LOSS, `=0` BE. OPEN ⇒ pas de `realized_rr`. `planned_rr > 0` si renseigné.
- `Decimal` en Python, `DecimalField` en base. Jamais de `float` pour RR/prix.
- Win rate = `W / (W + L) × 100` (BE exclus). Expectancy = moyenne de `realized_rr` des clôturés (BE = 0). Profit Factor = `Σ gains / |Σ pertes|`, **non défini** si aucune perte. Dénominateur nul ⇒ « non défini », jamais une valeur trompeuse.
- Trades OPEN **exclus** des stats clôturées. Filtres appliqués **avant** agrégation.
- Courbe cumulée : tri par `closed_at`, puis `created_at`, puis UUID (ordre stable).
- Détail : skill `trading-domain-rules`.

## Sécurité (dès le jour 1)

- Toute donnée métier a un propriétaire ; le `user` est déterminé **côté serveur**, jamais depuis le client. Filtrer tous les querysets par `request.user` (404, pas 403, sur ressource d'autrui).
- Auth par cookies HTTP-only + CSRF ; pas d'inscription publique (compte via commande d'admin).
- Captures : jamais en base (métadonnées + `storage_key` seulement), privées, servies après contrôle de permission ou URL signée courte ; valider type réel, taille, extension, contenu ; noms de stockage aléatoires.
- Secrets en variables d'environnement, jamais commités. PostgreSQL non exposé en prod. CORS restreint.

## Principes de code

- Vues DRF fines ; logique métier dans des **services** testables ; **selectors** légers pour lectures complexes.
- Pas de fichiers monolithiques, pas de fonctionnalité simulée, pas de bouton sans action. Si non implémenté, le dire.
- Ne pas réécrire du code déjà validé. Ne pas ajouter de dépendance sans valeur réelle.
- Hors périmètre MVP (ne pas développer) : brokers, import auto, IA, app native, SaaS multi-utilisateurs, facturation, trading automatique.

## Méthode de travail (chaque phase)

1. Rappeler l'objectif · 2. Décisions techniques · 3. Fichiers à créer/modifier · 4. Commandes exactes · 5. Contenu complet des fichiers · 6. Comment lancer · 7. Tests et résultats attendus · 8. Analyser les erreurs avant de continuer.

**Ne jamais affirmer qu'une commande ou un test a réussi sans sortie vérifiable.** Détail : skill `phase-workflow`.

## Interface

Français, dark mode par défaut (bleu-noir/graphite), vert = positif, rouge = négatif, gris = neutre ; responsive desktop/tablette/mobile ; bouton principal « Ajouter un trade ». Navigation : Dashboard, Journal, Analytics, Calendrier, Stratégies, Paramètres. Détail : skill `ui-dark-theme`.

## Skills du projet (`.claude/skills/`)

| Skill | Usage |
|---|---|
| `phase-workflow` | Déroulé et checklist de chaque phase (1→8) |
| `trading-domain-rules` | Statuts, R, formules, cas limites |
| `django-module` | Créer un module backend (modèle, service, selector, serializer, vue, tests) |
| `drf-auth-security` | Auth cookies/CSRF, isolation utilisateur, durcissement |
| `screenshots-storage` | Upload, abstraction de stockage, accès privé |
| `analytics-stats` | Services de calcul, endpoints, courbe d'equity |
| `nextjs-feature` | Feature frontend (RHF + Zod, services API, états vide/chargement/erreur) |
| `ui-dark-theme` | Design tokens, composants, accessibilité, responsive |
| `docker-env-setup` | Phase 2 : Compose, env, vérification des 3 services |
| `testing-strategy` | pytest / Vitest / Testing Library, cas limites, isolation |
| `backup-restore` | Sauvegarde/restauration PostgreSQL + captures |

Skills globaux utiles en complément : `security-review`, `code-review`, `frontend-design`, `deploy-vps`.

## Agents (niveau utilisateur, `~/.claude/agents/`)

`coder-backend`, `coder-frontend`, `coder-design`, `testeur` (après **chaque** livraison), `correcteur` (uniquement après rejet du testeur). Note : leurs descriptions parlent de « templates Django » ; ici le frontend est Next.js — le préciser dans le brief.

## Commandes

```bash
docker compose up -d --build                         # tous les services
docker compose up -d --build -V frontend             # après changement de dépendances npm (recrée node_modules)
docker compose exec backend pytest                   # 280 tests backend
docker compose exec backend python manage.py migrate
docker compose exec backend python manage.py createsuperuser
docker compose exec frontend npm test                # 279 tests frontend (Vitest)
```
Hors Docker, dans `frontend/` : `npm run typecheck | lint | build`.

## Pièges connus (ne pas les redécouvrir)

- **Desktop** : cookies renommés `tj_sessionid`/`tj_csrftoken` ; le proxy est `src/proxy.ts` (runtime, `x-tj-forwarded` pour que le backend détecte une requête non locale) ; tests desktop toujours avec `TJ_DATA_DIR` (jamais les vraies données) ; ne pas lancer de commande depuis `desktop/dist` (verrou du dossier au rebuild) ; une seule racine `tk.Tk()` par module de tests (en recréer échoue parfois) ; écrire les fichiers à antislashs avec Edit/Write, pas en heredoc.

- **Next 16 ≠ Next que tu connais** : lire `frontend/node_modules/next/dist/docs/` avant d'écrire du code Next. `cacheComponents`/`partialPrefetching` sont volontairement désactivés (app privée, rendu client).
- **Proxy same-origin** : le navigateur appelle `/api/v1/...` sur Next, qui relaie vers Django (`rewrites` dans `next.config.ts`). La règle doit garder le **slash final** (`/api/:path*/`), sinon Django redirige en boucle ; `skipTrailingSlashRedirect: true` est requis. Pas de `NEXT_PUBLIC_API_URL`.
- Les appels API utilisent `cache: "no-store"` (un 301 mis en cache par le navigateur avait cassé la session).
- **shadcn CLI** : a réécrit les imports vers un paquet npm tiers `cn` → corrigé en `@/lib/utils` (clsx + tailwind-merge). Revérifier après chaque `shadcn add`.
- `tw-animate-css` est importé par chemin relatif dans `globals.css` (son export `style` n'est pas résolu par le loader Turbopack).
- **Docker Desktop/Windows** : le rechargement à chaud exige `watchOptions.pollIntervalMs` (activé par `WATCHPACK_POLLING=true`).
- `AUTH_USER_MODEL` est `accounts.User` : ne jamais le changer après des migrations appliquées.
- **Captures** : jamais de `MEDIA_URL` ni de dossier servi statiquement ; l'image passe par `GET /screenshots/{id}/file/` (propriété vérifiée, 404 sinon). La suppression du fichier se fait en `transaction.on_commit` (un rollback ne perd rien). Les tests utilisent un stockage temporaire (fixture autouse) et `django_capture_on_commit_callbacks(execute=True)`. SVG et GIF sont refusés volontairement ; seule la 1re image des fichiers animés est conservée. Les fichiers orphelins (panne de suppression) sont journalisés, pas bloquants.
- **Analytics** : le backend est la seule source de vérité ; le frontend n'additionne ni ne moyenne rien (il ne convertit en nombre que pour la géométrie des graphiques ; les valeurs affichées sont les chaînes exactes du serveur). Égalités de total départagées par la clé (ordre alphabétique) dans les regroupements. Meilleur/pire trade : seulement s'il existe un gain/une perte. Courbe d'équité en segments droits (un lissage suggère des valeurs inexistantes). Trade modifié ⇒ invalidation des clés `["trades"]` **et** `["analytics"]`.
- **Tests analytics** : jeu de données « A » commenté dans `backend/tests/test_analytics_stats.py` (valeurs calculées à la main, repris dans `frontend/src/test/analytics-fixtures.ts`). Tester `shiftDate`/dates sous plusieurs `TZ` (la machine de dev est en UTC+0 et masque les bugs de fuseau).
- **Next 16 : la prop des fichiers `error.tsx` / `global-error.tsx` est `retry` (pas `reset`).** `global-error` remplace tout le document : `<html>`/`<body>` et styles en ligne obligatoires.
- **Radix `asChild` écrase `data-slot`** (ex. `SheetTrigger asChild` → `data-slot="sheet-trigger"`) : les styles génériques ciblent `[data-variant][data-size]`, pas `[data-slot="button"]`. `CardTitle` rend un vrai `<h2>`.
- **Calendrier** : un seul appel par mois (le payload contient les trades de chaque jour) ; jours calculés dans le fuseau de l'utilisateur côté backend ET `lib/calendar.ts` (arithmétique UTC pure, testée sous plusieurs `TZ`). Résumé du mois déduit des jours (cohérent avec la grille et avec `/analytics/overview/` sur le même mois : test dédié). Un jour sans trade clôturé a `total_r: null` (≠ 0 R ; un jour de break-even vaut 0 R).
- **Session expirée** : `createQueryClient()` (providers.tsx) met `["me"]` à `null` sur tout 401/403 hors requête « me », ce qui déclenche la redirection du layout ; un seul message grâce au test `getQueryData(ME_KEY) === null`.
- **Accessibilité** : `src/test/a11y.test.tsx` passe axe-core (WCAG 2 A/AA + bonnes pratiques) sur toutes les vues principales ; le contraste n'est PAS mesurable en jsdom (vérifié à la conception).
- **Tests d'upload frontend** : `FakeXHR` (`src/test/fake-xhr.ts`) ; `userEvent.setup({ applyAccept: false })` pour tester le refus côté client.
- Dates : saisies et affichées dans le fuseau de l'utilisateur (`lib/datetime.ts`), stockées en UTC.

## Version Windows

```bash
cd desktop && .venv\Scripts\python.exe -m pytest tests      # 162 tests
cd desktop && .venv\Scripts\python.exe build.py --no-installer
```
