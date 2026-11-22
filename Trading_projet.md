# Trading Journal --- Dossier de conception et prompt maître

**Version :** 1.0\
**Date :** 15 novembre 2026\
**Statut :** Architecture validée\
**Thème UI :** Dark mode professionnel\
**Plateforme :** Application web responsive\
**Usage initial :** Personnel, avec architecture évolutive

------------------------------------------------------------------------

## 1. Vision du produit

Trading Journal est une application web personnelle permettant de
consigner les opérations de trading, conserver plusieurs captures
d'écran par opération, documenter les décisions et analyser les
performances.

L'application doit répondre à quatre questions :

1.  Quels trades ont été pris ?
2.  Pourquoi ces trades ont-ils été pris ?
3.  Quels ont été leurs résultats ?
4.  Quelles leçons peut-on tirer des performances et de la discipline ?

La première version repose sur une saisie manuelle. Aucune connexion à
un broker n'est requise.

### Marchés pris en charge

-   Forex
-   Métaux, notamment XAUUSD
-   Indices
-   Cryptomonnaies

Les actifs doivent être configurables en texte afin de ne pas limiter
l'utilisateur à une liste rigide.

## 2. Décisions validées

  -----------------------------------------------------------------------
  Élément                             Décision
  ----------------------------------- -----------------------------------
  Plateforme                          Web responsive

  Utilisateurs                        Personnel au départ

  Marchés                             Forex, XAUUSD, indices, crypto

  RR                                  RR prévu et RR réalisé

  Captures                            Plusieurs par trade

  Saisie                              Manuelle

  Langue initiale                     Français

  Apparence                           Dark mode professionnel par défaut

  Architecture                        Monolithe modulaire

  Frontend                            Next.js, React, TypeScript

  Backend                             Python, Django, Django REST
                                      Framework

  Base de données                     PostgreSQL

  Images                              Stockage local en développement, S3
                                      compatible en production

  Conteneurisation                    Docker Compose
  -----------------------------------------------------------------------

## 3. Périmètre fonctionnel du MVP

### 3.1 Dashboard

Afficher les indicateurs calculés à partir des trades clôturés :

-   Nombre total de trades clôturés
-   Nombre de WIN, LOSS et BE
-   Win rate
-   RR moyen réalisé
-   Expectancy en R
-   Profit Factor en R, si calculable
-   Performance cumulée en R
-   Courbe de performance
-   Répartition par résultat
-   Derniers trades
-   Filtres par période, actif, marché et stratégie

Les trades OPEN ne doivent pas être intégrés aux statistiques de
performance clôturée.

### 3.2 Journal des trades

Fonctions :

-   Créer, consulter, modifier et supprimer un trade
-   Rechercher par nom ou actif
-   Filtrer par dates, marché, actif, direction, statut et stratégie
-   Trier et paginer les résultats
-   Accéder à la fiche détaillée d'un trade

Champs proposés :

  Champ         Type / règle
  ------------- -------------------------------------------------------
  id            UUID
  user          Relation obligatoire vers l'utilisateur
  name          Texte obligatoire
  trade_date    Date et heure avec fuseau géré
  market_type   FOREX, METALS, INDICES, CRYPTO
  asset         Texte obligatoire, ex. EURUSD, XAUUSD, NAS100, BTCUSD
  direction     BUY ou SELL
  status        OPEN, WIN, LOSS, BE
  planned_rr    Décimal positif, facultatif si besoin
  realized_rr   Décimal signé, nul pour BE, absent tant que OPEN
  strategy      Relation facultative vers Strategy
  entry_price   Décimal facultatif
  stop_loss     Décimal facultatif
  take_profit   Décimal facultatif
  notes         Texte facultatif
  created_at    Date de création
  updated_at    Date de modification
  closed_at     Date de clôture, facultative

Les prix ne sont pas obligatoires pour enregistrer un trade. Les calculs
de performance reposent d'abord sur le résultat exprimé en R.

### 3.3 Captures d'écran

Un trade peut posséder plusieurs captures.

Catégories :

-   BEFORE : avant le trade
-   DURING : pendant le trade
-   AFTER : après le trade

Métadonnées de chaque capture :

-   UUID
-   trade associé
-   clé de stockage
-   nom de fichier original
-   catégorie
-   description facultative
-   date d'ajout

Fonctions :

-   Sélection de plusieurs fichiers
-   Prévisualisation avant envoi
-   Upload avec progression
-   Galerie par trade
-   Affichage en grand format
-   Modification de la catégorie et de la description
-   Suppression individuelle

Les fichiers binaires ne sont jamais enregistrés dans PostgreSQL. La
base conserve les métadonnées et la clé de stockage. Les fichiers sont
privés et servis après contrôle des permissions.

Valider le type réel du fichier, la taille, l'extension et le contenu.
Générer des noms de stockage aléatoires et sûrs. Prévoir une limite de
taille configurable.

### 3.4 Stratégies

Chaque stratégie comporte :

-   UUID
-   utilisateur propriétaire
-   nom
-   description
-   règles d'entrée facultatives
-   règles de sortie facultatives
-   statut actif/inactif
-   dates de création et modification

Une stratégie désactivée reste associée aux anciens trades. La
suppression d'une stratégie ne doit pas supprimer l'historique des
trades : utiliser une relation nullable ou une désactivation selon le
choix final de modélisation.

### 3.5 Analytics

Indicateurs :

-   Win rate
-   Nombre de WIN, LOSS, BE et OPEN
-   RR moyen réalisé
-   Gain moyen en R
-   Perte moyenne en R
-   Expectancy en R
-   Profit Factor en R
-   Performance cumulée en R
-   Meilleure et pire opération
-   Séries de gains et de pertes
-   Résultats par actif, marché et stratégie
-   Résultats par période

Ne pas afficher une statistique si les données requises sont absentes ou
si son dénominateur est nul. Afficher un état « non disponible » ou «
non défini » plutôt qu'une valeur trompeuse.

### 3.6 Calendrier

-   Vue mensuelle
-   Indication des jours avec trades
-   Résultat quotidien en R
-   Consultation des trades d'une journée
-   Navigation entre les mois
-   Filtres éventuels par marché et stratégie

### 3.7 Paramètres

-   Profil utilisateur
-   Préférences d'affichage
-   Dark mode par défaut
-   Fuseau horaire d'affichage
-   Configuration et sécurité du compte
-   Sauvegarde et restauration documentées

## 4. Règles métier et statistiques

### 4.1 Cycle de vie d'un trade

Statuts :

-   OPEN : trade encore ouvert
-   WIN : trade clôturé avec un résultat positif
-   LOSS : trade clôturé avec un résultat négatif
-   BE : trade clôturé à zéro

Règles :

-   Un trade OPEN ne possède pas de `realized_rr` définitif.
-   À la clôture, `realized_rr` doit être renseigné.
-   `realized_rr > 0` implique WIN.
-   `realized_rr < 0` implique LOSS.
-   `realized_rr = 0` implique BE.
-   Le statut est déterminé côté backend à partir du RR réalisé, et non
    librement choisi par le frontend.
-   Le RR prévu est strictement positif lorsqu'il est renseigné.
-   Les calculs utilisent Decimal côté backend et un type décimal adapté
    en base.

### 4.2 Unité de risque R

Le résultat réalisé est exprimé en multiple du risque initial :

-   +3R : gain égal à trois fois le risque
-   -1R : perte égale au risque initial
-   0R : Break Even

La performance en R permet de comparer des opérations sans mélanger les
devises ou les tailles de position.

### 4.3 Formules

Soit `N_closed` le nombre de trades clôturés WIN, LOSS ou BE.

**Win rate** --- les BE sont exclus du dénominateur :

`Wins / (Wins + Losses) × 100`

Si aucun WIN ou LOSS n'existe, le win rate est non défini.

**RR moyen réalisé / Expectancy en R :**

`Somme des realized_rr de tous les trades clôturés / Nombre de trades clôturés`

Les BE comptent comme zéro dans cette moyenne.

**Gain moyen en R :**

`Somme des realized_rr positifs / Nombre de WIN`

**Perte moyenne en R :**

`Somme des realized_rr négatifs / Nombre de LOSS`

Le résultat peut être affiché signé ou en valeur absolue, mais son
libellé doit préciser la convention.

**Profit Factor en R :**

`Somme des realized_rr positifs / Valeur absolue de la somme des realized_rr négatifs`

Si aucune perte n'existe, le profit factor est non défini, et non
infini.

**Performance cumulée :**

Trier les trades clôturés par date de clôture, puis calculer la somme
cumulative des `realized_rr`.

Définir explicitement l'ordre secondaire en cas de dates identiques (par
exemple `created_at`, puis UUID) pour garantir un résultat stable.

Les statistiques filtrées doivent appliquer les filtres avant les
agrégations. Le backend est la source de vérité des calculs.

## 5. Architecture technique

### 5.1 Style architectural

Adopter un **monolithe modulaire** avec séparation des responsabilités.
Ne pas créer de microservices pour le MVP.

Avantages recherchés :

-   Développement et déploiement simples
-   Tests plus faciles
-   Frontières métier claires
-   Possibilité d'extraire un module plus tard si une raison réelle
    apparaît
-   Pas de complexité d'infrastructure inutile

### 5.2 Frontend

-   Next.js avec App Router
-   React
-   TypeScript strict
-   Tailwind CSS
-   shadcn/ui
-   Recharts
-   React Hook Form
-   Zod

Responsabilités :

-   Présentation responsive
-   Navigation
-   Formulaires et validation utilisateur
-   Visualisation des statistiques
-   Gestion des états de chargement, erreur et absence de données
-   Appels à l'API

La validation frontend améliore l'expérience, mais le backend reste
responsable de la validation métier.

### 5.3 Backend

-   Python
-   Django
-   Django REST Framework
-   Documentation OpenAPI / Swagger
-   Tests avec pytest et outils adaptés à Django

Responsabilités :

-   Authentification et autorisation
-   Validation métier
-   Persistance
-   Gestion des captures
-   Calcul des statistiques
-   Filtrage, pagination et recherche
-   Journalisation des erreurs

Les vues ne doivent pas contenir toute la logique métier. Utiliser des
services pour les opérations métier et des selectors/repositories légers
si cela clarifie les lectures complexes. Éviter les couches abstraites
sans utilité.

### 5.4 Base de données

PostgreSQL avec Django ORM et migrations versionnées.

Principes :

-   UUID comme identifiants
-   Contraintes de cohérence
-   Index sur les champs fréquemment filtrés
-   Relations explicites
-   Champs décimaux pour les valeurs financières et RR
-   Transactions pour les opérations qui modifient plusieurs ressources
-   Toutes les données métier associées à un propriétaire utilisateur

### 5.5 Stockage des images

Définir une interface de stockage afin de pouvoir utiliser :

-   Stockage local en développement
-   Stockage S3 compatible en production

Le code métier ne doit pas dépendre directement d'un fournisseur. Les
captures sont privées et l'accès passe par une autorisation contrôlée ou
des URL signées de courte durée.

### 5.6 Infrastructure

-   Dockerfile frontend
-   Dockerfile backend
-   Docker Compose
-   PostgreSQL
-   Volumes persistants en développement
-   `.env.example`
-   Configuration distincte développement / production
-   README d'installation
-   Procédure de sauvegarde et restauration

Ne pas exposer PostgreSQL publiquement en production. Ne jamais
committer de secrets.

## 6. Modèle de données conceptuel

Entités principales :

1.  User
2.  Trade
3.  TradeScreenshot
4.  Strategy

Relations :

-   User 1 --- N Trade
-   User 1 --- N Strategy
-   Strategy 1 --- N Trade (relation facultative sur Trade)
-   Trade 1 --- N TradeScreenshot

### Trade

Champs essentiels :

-   id: UUID
-   user_id: FK obligatoire
-   strategy_id: FK facultative
-   name
-   trade_date
-   market_type
-   asset
-   direction
-   status
-   planned_rr
-   realized_rr
-   entry_price facultatif
-   stop_loss facultatif
-   take_profit facultatif
-   notes
-   created_at
-   updated_at
-   closed_at facultatif

### TradeScreenshot

-   id: UUID
-   trade_id: FK obligatoire
-   storage_key
-   original_filename
-   category
-   description
-   uploaded_at

### Strategy

-   id: UUID
-   user_id: FK obligatoire
-   name
-   description
-   entry_rules facultatif
-   exit_rules facultatif
-   is_active
-   created_at
-   updated_at

### Sécurité des relations

Toute lecture, modification ou suppression d'un trade, d'une stratégie
ou d'une capture doit vérifier que la ressource appartient à
l'utilisateur authentifié. Ne jamais faire confiance à un `user_id`
fourni par le client : le propriétaire doit être déterminé côté serveur.

## 7. Structure des dossiers cible

``` text
trading-journal/
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   │   ├── (auth)/
│   │   │   └── (dashboard)/
│   │   │       ├── dashboard/
│   │   │       ├── trades/
│   │   │       ├── analytics/
│   │   │       ├── calendar/
│   │   │       ├── strategies/
│   │   │       └── settings/
│   │   ├── components/
│   │   │   ├── ui/
│   │   │   ├── layout/
│   │   │   └── shared/
│   │   ├── features/
│   │   │   ├── trades/
│   │   │   ├── screenshots/
│   │   │   ├── analytics/
│   │   │   ├── strategies/
│   │   │   └── calendar/
│   │   ├── services/
│   │   ├── hooks/
│   │   ├── schemas/
│   │   ├── types/
│   │   └── lib/
│   ├── public/
│   ├── package.json
│   └── Dockerfile
├── backend/
│   ├── config/
│   │   ├── settings/
│   │   ├── urls.py
│   │   └── wsgi.py
│   ├── apps/
│   │   ├── accounts/
│   │   ├── trades/
│   │   ├── strategies/
│   │   ├── screenshots/
│   │   └── analytics/
│   ├── core/
│   ├── tests/
│   ├── manage.py
│   ├── requirements/
│   └── Dockerfile
├── storage/
├── docs/
│   ├── architecture.md
│   ├── database.md
│   ├── api.md
│   └── deployment.md
├── docker-compose.yml
├── .env.example
├── .gitignore
└── README.md
```

Cette arborescence est une cible. L'agent doit vérifier la cohérence
avec les conventions réelles des versions de Next.js et Django retenues,
et éviter de créer des dossiers vides ou des abstractions prématurées.

## 8. API REST prévue

Préfixe : `/api/v1/`

### Authentification

-   `POST /auth/login/`
-   `POST /auth/logout/`
-   `GET /auth/me/`
-   `POST /auth/refresh/` si une stratégie de jetons avec refresh est
    retenue

Privilégier des cookies sécurisés HTTP-only et une protection CSRF
adaptée. Documenter clairement le fonctionnement des sessions.
Désactiver l'inscription publique dans le MVP ; créer le compte
personnel via une commande d'administration.

### Trades

-   `GET /trades/`
-   `POST /trades/`
-   `GET /trades/{id}/`
-   `PATCH /trades/{id}/`
-   `DELETE /trades/{id}/`

Filtres prévus : marché, actif, direction, statut, stratégie, date de
début, date de fin. Ajouter pagination et tri côté serveur.

### Captures

-   `GET /trades/{id}/screenshots/`
-   `POST /trades/{id}/screenshots/`
-   `PATCH /screenshots/{id}/`
-   `DELETE /screenshots/{id}/`

### Stratégies

-   `GET /strategies/`
-   `POST /strategies/`
-   `GET /strategies/{id}/`
-   `PATCH /strategies/{id}/`
-   `DELETE /strategies/{id}/` ou désactivation selon les règles de
    conservation

### Analytics

-   `GET /analytics/overview/`
-   `GET /analytics/performance/`
-   `GET /analytics/equity-curve/`
-   `GET /analytics/by-asset/`
-   `GET /analytics/by-strategy/`
-   `GET /analytics/by-period/`

Documenter les paramètres, les réponses, les erreurs et les règles de
calcul avec OpenAPI.

## 9. UX/UI --- Direction artistique

Créer une interface de journal de trading moderne, professionnelle et
sobre.

### Direction visuelle

-   Dark mode par défaut
-   Fond sombre bleu-noir ou graphite
-   Surfaces et cartes légèrement différenciées
-   Typographie très lisible
-   Espacements cohérents
-   Vert pour les résultats positifs
-   Rouge pour les résultats négatifs
-   Gris pour les informations neutres
-   Couleurs utilisées avec parcimonie
-   Contrastes accessibles
-   Graphiques lisibles
-   Interface responsive desktop, tablette et mobile

Ne pas surcharger le dashboard. Les indicateurs les plus importants
doivent être immédiatement visibles.

### Navigation

-   Dashboard
-   Journal des trades
-   Analytics
-   Calendrier
-   Stratégies
-   Paramètres

Prévoir un bouton d'action principal « Ajouter un trade ».

### Expérience utilisateur

-   Formulaires clairs avec erreurs explicites
-   Confirmation avant suppression
-   Prévisualisation des images
-   Upload multiple avec progression
-   États de chargement
-   États vides utiles
-   Notifications de succès et d'échec
-   Navigation clavier et accessibilité de base
-   Mise en page mobile pensée spécifiquement

## 10. Sécurité et qualité

Exigences :

-   Authentification sécurisée
-   Autorisation par ressource et propriétaire
-   Protection CSRF si authentification par cookies
-   HTTPS en production
-   Validation stricte des entrées côté backend
-   Protection des uploads (format réel, taille, nom, contenu)
-   Fichiers privés
-   Secrets dans variables d'environnement
-   CORS limité aux origines nécessaires
-   Gestion centralisée des erreurs
-   Logs sans secrets ni données sensibles inutiles
-   Sauvegardes et procédure de restauration testée
-   Migrations versionnées
-   Dépendances maîtrisées et mises à jour documentées

## 11. Tests et critères d'acceptation

### Backend

-   Tests des modèles et contraintes
-   Tests de création, modification et suppression
-   Tests des règles OPEN/WIN/LOSS/BE
-   Tests des calculs statistiques, y compris les cas limites
-   Tests des filtres et de la pagination
-   Tests d'autorisation et d'isolation utilisateur
-   Tests d'upload, d'accès et de suppression des captures
-   Tests des transactions et erreurs

### Frontend

-   Tests des formulaires
-   Tests des composants critiques
-   Tests des états vides, chargement et erreurs
-   Tests des interactions de galerie
-   Tests des filtres et navigation
-   Vérification responsive

### Scénarios d'acceptation

1.  L'utilisateur peut se connecter à son compte.
2.  Il peut créer un trade OPEN.
3.  Il peut ajouter plusieurs captures classées BEFORE, DURING et AFTER.
4.  Il peut clôturer le trade avec un RR réalisé.
5.  Le backend détermine le statut de clôture.
6.  Le trade apparaît dans l'historique.
7.  Les statistiques sont recalculées correctement.
8.  Les trades OPEN sont exclus des statistiques de performance
    clôturée.
9.  Un utilisateur ne peut jamais consulter les ressources d'un autre
    utilisateur.
10. Les données et captures restent disponibles après redémarrage des
    services et restauration d'une sauvegarde.

## 12. Plan de développement

### Phase 1 --- Conception

-   Cahier des charges
-   Architecture
-   Modèle de données
-   Règles métier
-   Contrats API
-   Structure du dépôt

**Livrable :** dossier de conception validé.

### Phase 2 --- Initialisation

-   Création du dépôt
-   Initialisation Next.js
-   Initialisation Django
-   Configuration PostgreSQL
-   Docker Compose
-   Variables d'environnement
-   Vérification de communication entre services

**Livrable :** squelette de projet fonctionnel.

### Phase 3 --- Backend

-   Modèles
-   Migrations
-   Authentification
-   API des trades
-   Stratégies
-   Permissions
-   Tests

**Livrable :** backend testable via API.

### Phase 4 --- Frontend

-   Layout et navigation
-   Design system
-   Formulaires
-   Journal et détails
-   Connexion à l'API

**Livrable :** parcours principal fonctionnel.

### Phase 5 --- Captures d'écran

-   Stockage
-   Upload multiple
-   Galerie
-   Contrôle d'accès
-   Tests

**Livrable :** gestion complète des images.

### Phase 6 --- Dashboard et analytics

-   Services de calcul
-   Endpoints statistiques
-   Graphiques
-   Filtres temporels

**Livrable :** tableau de bord fiable.

### Phase 7 --- Calendrier et finitions

-   Calendrier
-   Expérience mobile
-   Gestion des erreurs
-   Accessibilité

**Livrable :** MVP complet.

### Phase 8 --- Validation et déploiement

-   Tests complets
-   Sécurité
-   Sauvegardes
-   Documentation
-   Déploiement

**Livrable :** application prête à être utilisée.

## 13. Éléments reportés après le MVP

Ne pas développer maintenant :

-   Connexion automatique aux brokers
-   Import automatique des transactions
-   Analyse IA des captures ou des trades
-   Application mobile native
-   Multi-utilisateurs public / SaaS
-   Facturation et abonnements
-   Trading automatique ou exécution d'ordres

L'architecture doit permettre d'envisager ces évolutions ultérieurement
sans les anticiper par une complexité inutile.

------------------------------------------------------------------------

# 14. PROMPT MAÎTRE --- À UTILISER AVEC L'AGENT DE DÉVELOPPEMENT

Tu es un Software Architect senior et développeur Full-Stack. Tu dois
construire le projet Trading Journal en respectant intégralement le
dossier de conception ci-dessus.

## Objectif

Livrer une application web personnelle de journal de trading, fiable,
sécurisée, responsive, maintenable et évolutive.

## Stack obligatoire

-   Next.js App Router
-   React
-   TypeScript strict
-   Tailwind CSS
-   shadcn/ui
-   Recharts
-   React Hook Form
-   Zod
-   Python
-   Django
-   Django REST Framework
-   PostgreSQL
-   Stockage local abstrait en développement et S3 compatible en
    production
-   Docker Compose

## Principes d'architecture obligatoires

1.  Utiliser un monolithe modulaire, pas des microservices.
2.  Séparer clairement présentation, logique métier, accès aux données
    et infrastructure.
3.  Garder les vues API fines ; placer les règles métier dans des
    services testables.
4.  Utiliser Decimal pour les RR et calculs financiers.
5.  Faire du backend la source de vérité des statuts et statistiques.
6.  Isoler toutes les données par utilisateur dès le premier jour.
7.  Ne jamais stocker les images binaires dans PostgreSQL.
8.  Ne jamais exposer les captures privées sans autorisation.
9.  Versionner les migrations et documenter les API.
10. Éviter les abstractions et dépendances qui n'apportent pas de valeur
    réelle.

## Méthode de travail impérative

Travaille par phases et par petits incréments.

Pour chaque phase :

1.  Rappelle l'objectif.
2.  Explique les décisions techniques.
3.  Indique les fichiers à créer ou modifier.
4.  Donne les commandes exactes à exécuter.
5.  Fournis le contenu complet des fichiers concernés.
6.  Explique comment lancer les services.
7.  Donne les tests à exécuter et les résultats attendus.
8.  Analyse les erreurs éventuelles avant de poursuivre.

Ne prétends jamais qu'une commande ou un test a réussi sans résultat
vérifiable.

Ne passe jamais à la phase suivante sans validation explicite de
l'utilisateur.

Ne réécris pas inutilement du code déjà validé. Ne crée pas de fichiers
monolithiques. Ne laisse pas de fonctionnalités simulées ou de boutons
sans action réelle. Si une fonctionnalité n'est pas encore implémentée,
l'indiquer clairement.

Si une exigence est ambiguë, pose une question ciblée avant de prendre
une décision structurante. Pour les détails mineurs, propose un choix
raisonnable et explique-le.

## Première tâche de l'agent

La conception fonctionnelle et l'architecture ont déjà été validées.

Commence maintenant par la **PHASE 2 --- Initialisation du projet**.

Avant de générer les fichiers :

1.  Vérifie les versions stables et compatibles des technologies
    retenues.
2.  Présente les choix de versions et les dépendances principales.
3.  Présente les prérequis locaux.
4.  Propose les commandes exactes pour créer le dépôt et initialiser
    frontend et backend.
5.  Définis le Docker Compose initial et les variables d'environnement
    nécessaires.
6.  Explique comment vérifier que Next.js, Django et PostgreSQL
    fonctionnent ensemble.

Ne développe pas encore les modules métier complets. L'objectif de cette
phase est d'obtenir un environnement propre, reproductible et
fonctionnel.

Attends la validation de l'utilisateur à chaque étape importante.

**Résultat final attendu :** un Trading Journal réellement utilisable,
dont le code est documenté, testé, sécurisé et facile à faire évoluer.
