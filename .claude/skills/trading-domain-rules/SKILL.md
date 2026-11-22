---
name: trading-domain-rules
description: Règles métier du Trading Journal — cycle de vie OPEN/WIN/LOSS/BE, unité de risque R, formules statistiques et cas limites. À utiliser pour tout code touchant trades, statuts, RR ou statistiques.
---

# Règles métier

## Cycle de vie
- Statuts : `OPEN`, `WIN`, `LOSS`, `BE`.
- OPEN : pas de `realized_rr` définitif, `closed_at` vide.
- Clôture : `realized_rr` obligatoire ; statut **calculé côté backend** :
  - `> 0` → WIN · `< 0` → LOSS · `== 0` → BE
- Le client ne choisit jamais le statut de clôture (ignorer/refuser ce champ en écriture).
- `planned_rr` : strictement positif si renseigné, facultatif.
- Prix (`entry_price`, `stop_loss`, `take_profit`) facultatifs ; les stats reposent sur le R.
- **Réouverture autorisée (décision validée)** : `PATCH realized_rr: null` remet le trade en OPEN et efface `closed_at`. Corriger un RR déjà clôturé recalcule le statut et conserve `closed_at`.
- **Séries WIN/LOSS consécutives : les BE sont ignorés** (ni rupture ni prolongation). Décision validée.

## Implémentation attendue
- Une fonction pure `derive_status(realized_rr: Decimal | None) -> Status` dans `apps/trades/services/`.
- Contrainte DB (CheckConstraint) : `status = OPEN ⇔ realized_rr IS NULL`, `planned_rr IS NULL OR planned_rr > 0`.
- `Decimal` partout (jamais `float`) ; sérialiseurs DRF avec `coerce_to_string` cohérent ; `DecimalField(max_digits, decimal_places)` choisis et documentés.
- `trade_date` timezone-aware (`USE_TZ = True`).

## Formules (N = trades clôturés WIN/LOSS/BE)
| Indicateur | Formule | Non défini si |
|---|---|---|
| Win rate | `W / (W + L) × 100` (BE exclus) | `W + L = 0` |
| Expectancy / RR moyen réalisé | `Σ realized_rr / N` (BE = 0) | `N = 0` |
| Gain moyen | `Σ rr>0 / #WIN` | `#WIN = 0` |
| Perte moyenne | `Σ rr<0 / #LOSS` (signée ; libeller la convention) | `#LOSS = 0` |
| Profit Factor | `Σ rr>0 / |Σ rr<0|` | aucune perte (pas d'infini) |
| Perf. cumulée | somme cumulative triée par `closed_at`, puis `created_at`, puis `id` | — |

- OPEN **exclus** de toutes les stats clôturées (mais comptés dans le décompte par statut).
- Filtres (période, actif, marché, stratégie) appliqués **avant** agrégation.
- Retourner `null` + indicateur « non défini » plutôt que 0 ou ∞ ; le frontend affiche « Non disponible ».

## Cas limites à tester
Aucun trade · uniquement des BE · uniquement des WIN (PF non défini) · uniquement des LOSS · RR très petits/grands · mêmes `closed_at` (ordre stable) · trades OPEN mélangés · changement de fuseau en limite de jour.
