---
name: ui-dark-theme
description: Direction artistique et design system du Trading Journal — dark mode professionnel, tokens Tailwind/shadcn, couleurs gain/perte, navigation, responsive et accessibilité. À utiliser pour tout travail visuel ou de mise en page.
---

# Design — Dark mode professionnel

## Principes
- Dark par défaut, sobre, lisible ; couleurs avec parcimonie ; indicateurs clés visibles immédiatement ; ne pas surcharger le dashboard.
- Langue : français. Libellés de statut : OPEN « Ouvert », WIN « Gagnant », LOSS « Perdant », BE « Break-even ».

## Tokens (variables CSS shadcn, à définir dans `globals.css`, thème `.dark` par défaut)
| Rôle | Intention |
|---|---|
| `--background` | bleu-noir/graphite (ex. ~`#0b0f17`) |
| `--card` / `--popover` | légèrement plus clair que le fond (~`#111827`) |
| `--border` | gris bleuté discret |
| `--foreground` / `--muted-foreground` | texte principal / secondaire |
| `--positive` | vert (gains, WIN) |
| `--negative` | rouge (pertes, LOSS) |
| `--neutral` | gris (BE, OPEN, infos neutres) |
| `--primary` | accent unique (bleu/indigo) pour actions |

Les valeurs exactes sont à fixer en phase 4 et vérifiées pour un contraste **WCAG AA** (4.5:1 texte, 3:1 éléments UI). Ne jamais coder l'information par la couleur seule : ajouter signe (+/−), icône ou libellé (accessibilité daltonisme).

## Mise en page
- Desktop : sidebar fixe (Dashboard, Journal, Analytics, Calendrier, Stratégies, Paramètres) + zone de contenu.
- Mobile : barre de navigation basse ou menu repliable, **conçu spécifiquement** (pas un simple rétrécissement) ; tableaux → cartes empilées ; formulaires en une colonne ; cibles tactiles ≥ 44 px.
- Bouton principal « Ajouter un trade » toujours accessible (header desktop, FAB/bouton fixe mobile).
- Espacements sur grille cohérente (échelle Tailwind), typographie très lisible (chiffres tabulaires `tabular-nums` pour R, prix, stats).

## Composants
shadcn/ui : Button, Card, Dialog/AlertDialog (confirmation suppression), Table, Tabs, Select, Calendar/Popover (dates), Badge (statuts), Skeleton, Toast/Sonner, DropdownMenu, Form. Badges de statut : WIN vert, LOSS rouge, BE/OPEN gris.

## Graphiques (Recharts)
Fond transparent, grille discrète, courbe d'equity avec zone vert/rouge selon signe, tooltips lisibles, légendes claires, état vide explicite. Voir skill global `dataviz` pour les palettes accessibles.

## Accessibilité de base
Focus visible, ordre de tabulation logique, `aria-label` sur icônes seules, dialogues avec piégeage du focus, `prefers-reduced-motion` respecté.

## Compléments
Skills globaux : `frontend-design` (esthétique), `ui-ux-design` (parcours), `frontend-expert` (code) ; agent `coder-design`.
