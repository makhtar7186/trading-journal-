---
name: phase-workflow
description: Déroulé et checklist des 8 phases du projet Trading Journal (conception → déploiement). À utiliser au début de toute phase, pour savoir quoi livrer, quoi valider et quand s'arrêter.
---

# Workflow par phases — Trading Journal

Règle d'or : **une phase à la fois, validation explicite de l'utilisateur avant la suivante.** Petits incréments, pas de réécriture du code validé.

## Gabarit de réponse pour chaque phase
1. Objectif de la phase
2. Décisions techniques (et pourquoi)
3. Fichiers à créer / modifier
4. Commandes exactes
5. Contenu complet des fichiers
6. Comment lancer les services
7. Tests à exécuter + résultat attendu
8. Analyse des erreurs avant de poursuivre

Ne jamais dire « ça marche » sans sortie de commande réelle. Si une fonctionnalité n'est pas faite, l'écrire clairement.

## Phases et livrables
| # | Phase | Contenu | Livrable |
|---|---|---|---|
| 1 | Conception | Cahier, archi, modèle, API | Dossier validé ✅ |
| 2 | Initialisation | Dépôt, Next.js, Django, PostgreSQL, Compose, env | Squelette fonctionnel (voir `docker-env-setup`) |
| 3 | Backend | Modèles, migrations, auth, API trades/stratégies, permissions, tests | Backend testable via API |
| 4 | Frontend | Layout, design system, formulaires, journal, détail, API | Parcours principal |
| 5 | Captures | Stockage, upload multiple, galerie, accès, tests | Gestion complète des images |
| 6 | Analytics | Services de calcul, endpoints, graphiques, filtres | Dashboard fiable |
| 7 | Calendrier & finitions | Calendrier, mobile, erreurs, accessibilité | MVP complet |
| 8 | Validation & déploiement | Tests, sécurité, sauvegardes, doc, déploiement | Prêt à l'usage |

## Fin de phase
- Tests exécutés et résultats montrés.
- Délégation conseillée : `coder-*` → `testeur` (toujours) → `correcteur` seulement après rejet.
- Résumer ce qui est fait / non fait / non vérifié, puis **demander la validation**.
