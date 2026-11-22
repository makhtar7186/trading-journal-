---
name: analytics-stats
description: Implémentation des statistiques et endpoints analytics du Trading Journal (overview, performance, equity-curve, by-asset, by-strategy, by-period) et de leur affichage dashboard/calendrier. À utiliser pour la phase 6 et le calendrier.
---

# Analytics

Formules et cas limites : voir `trading-domain-rules` (à respecter à la lettre).

## Backend (`apps/analytics/`)
- `selectors.py` : construit le queryset filtré (user, période, actif, marché, stratégie) **puis** agrège ; restreint aux trades clôturés pour les stats de performance.
- `services.py` : fonctions pures de calcul sur des `Decimal` (win rate, expectancy, PF, gain/perte moyens, séries, meilleur/pire trade, cumul). Testables sans HTTP ni DB quand c'est possible.
- Agrégations en base (`Sum`, `Count`, `Case/When`, `TruncDay/Week/Month`) plutôt que boucles Python sur de gros volumes ; l'ordre cumulé final reste `closed_at`, `created_at`, `id`.
- Réponses JSON : valeurs `Decimal` sérialisées en chaîne, valeurs non définies = `null` (+ champ explicite si utile), jamais `Infinity`/`NaN`.
- Endpoints (préfixe `/api/v1/analytics/`) : `overview/`, `performance/`, `equity-curve/`, `by-asset/`, `by-strategy/`, `by-period/` ; mêmes paramètres de filtre que `/trades/` (`date_from`, `date_to`, `market_type`, `asset`, `strategy`).
- Séries WIN/LOSS consécutives : les BE sont **ignorés** (décision validée : ni rupture, ni prolongation).
- Calendrier : endpoint ou paramètre de `by-period` renvoyant par jour `{date, total_r, trade_count}` ; jours bornés selon le **fuseau d'affichage** de l'utilisateur (paramètre des réglages).
- OpenAPI : décrire chaque paramètre, réponse et règle de calcul.

## Frontend (`features/analytics`, `features/calendar`)
- Cartes KPI (win rate, expectancy, PF, total R, nb trades) ; un KPI `null` affiche « Non disponible » (pas 0).
- Recharts : courbe d'equity (cumul R), répartition WIN/LOSS/BE (camembert/barres), barres par actif/stratégie/période. Vert/rouge selon signe, axes lisibles, tooltips accessibles, résumé texte pour lecteurs d'écran.
- Filtres synchronisés dans l'URL (query params) ; états chargement/vide/erreur pour chaque widget.
- Calendrier mensuel : navigation mois, jours avec trades marqués, R du jour coloré, clic → trades du jour.

## Tests
Jeu de données connu avec résultats calculés à la main ; cas limites listés dans `trading-domain-rules` ; filtres avant agrégation ; OPEN exclus ; isolation utilisateur ; ordre stable à dates égales.
