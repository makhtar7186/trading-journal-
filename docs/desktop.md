# Version Windows (exécutable)

Trading Journal peut être distribué comme application Windows autonome : un lanceur qui, au **premier démarrage**, vérifie la présence de PostgreSQL, l'installe et le configure si besoin, crée la base, puis démarre l'application et propose de créer un compte. Aucun Docker, Python ni Node n'est requis sur le poste de l'utilisateur.

## Ce que fait le lanceur

1. **Instance unique** : relancer l'application ouvre simplement le navigateur.
2. **PostgreSQL** (premier lancement uniquement) :
   - détecte un serveur déjà installé (service Windows ou port 5432) ;
   - sinon propose d'installer PostgreSQL 17 : téléchargement de l'installateur officiel EnterpriseDB (HTTPS), contrôle **SHA-256 + signature Authenticode** (éditeur EnterpriseDB) avant toute exécution, puis installation silencieuse (une seule demande UAC) ;
   - ou permet d'utiliser un serveur existant (hôte, port, compte autorisé à créer une base et un rôle).
3. Crée une base `trading_journal` et un **rôle applicatif sans privilège de superutilisateur**. Le mot de passe superutilisateur n'est jamais écrit en clair.
4. Génère la clé secrète Django, applique les migrations, démarre l'API (waitress) et l'interface (Next.js) sur `127.0.0.1` uniquement.
5. Assistant de **création de compte** (peut être reporté). Un lien « Créer un compte » existe aussi sur la page de connexion ; il n'est accepté **que depuis la machine locale**.
6. Sauvegarde automatique périodique (`.tjbackup`) ; sauvegarde/restauration manuelles depuis la fenêtre du lanceur.

Les serveurs enfants sont rattachés à un Job Windows : si le lanceur est fermé de force, ils sont arrêtés avec lui (aucun port orphelin).

## Mode de secours SQLite et migration vers PostgreSQL

Si PostgreSQL **n'a jamais pu être configuré** au premier lancement (pas d'Internet, droits administrateur refusés, signature de l'installateur invalide, mot de passe `postgres` inconnu…), l'application propose de continuer avec une base **SQLite** (`trading_journal.sqlite3` dans le dossier de données). L'utilisateur confirme ; sinon le lanceur s'arrête avec l'erreur d'origine.

- **Repli uniquement au premier réglage.** Si PostgreSQL fonctionnait et ne répond plus, l'application **ne bascule pas** sur une base SQLite vide (l'utilisateur croirait avoir perdu ses données) : elle affiche l'erreur et demande de réparer le serveur.
- **Retour à PostgreSQL.** À chaque lancement en mode SQLite, si PostgreSQL est déjà présent ou si la connexion Internet est rétablie, une fenêtre propose « Passer à PostgreSQL maintenant » ou « Plus tard » (nouvelle proposition au plus une fois par jour). Un échec n'empêche jamais le démarrage : on reste sur SQLite.
- **Migration** (SQLite → PostgreSQL), dans cet ordre : sauvegarde `avant-migration-postgresql-….tjbackup` ; schéma à jour des deux côtés ; export JSON ; import en **une seule transaction** ; contrôle du nombre de lignes de chaque table ; seulement alors, la configuration bascule sur PostgreSQL. La base SQLite n'est jamais supprimée : elle est renommée `trading_journal.sqlite3.migre-vers-postgresql`. En cas d'échec, la base PostgreSQL est vidée (elle était vide) et SQLite reste actif. Une base PostgreSQL contenant déjà des données différentes n'est **jamais** écrasée.
- Les sessions ne sont pas migrées : il faut se reconnecter une fois. Les captures restent dans le même dossier `storage\`.
- **Sauvegardes** : en mode SQLite, `.tjbackup` contient `db.sqlite3` (copie cohérente même base ouverte). Une sauvegarde ne se restaure que dans le même type de base (refus explicite sinon).
- **Limite SQLite** : les décimaux sont stockés sous forme numérique (précision ≈ 15 chiffres significatifs) ; sans effet pour des prix et des RR réalistes (vérifié : `1.08123456`, `67123.45678901` migrés à l'identique). La recherche d'actif insensible à la casse ne gère que l'ASCII.

## Emplacements

| Élément | Chemin |
|---|---|
| Données | `%LOCALAPPDATA%\TradingJournal` (surcharge : variable `TJ_DATA_DIR`) |
| Configuration | `config.json` (secrets chiffrés avec DPAPI, liés à la session Windows) |
| Journaux | `logs\` (aucun secret) |
| Captures | `storage\` |
| Sauvegardes | `backups\` |

La désinstallation **ne supprime pas** les données.

## Construire

Prérequis : Windows 64 bits, Python 3.13 (venv `desktop\.venv`), Node 22, npm.

```bash
cd desktop
.venv\Scripts\python.exe -m pip install -r requirements-build.txt
.venv\Scripts\python.exe build.py --no-installer     # dossier desktop\dist\TradingJournal\ (≈ 210 Mo)
.venv\Scripts\python.exe build.py                    # + Setup.exe (nécessite Inno Setup 6)
.venv\Scripts\python.exe build.py --iscc "C:\chemin\ISCC.exe"
```

Vérification rapide du build : `dist\TradingJournal\tjctl.exe self-test`.

## Tests

```bash
cd desktop
.venv\Scripts\python.exe -m pytest tests
```

Les tests de migration réelle (`test_integration_migration.py`) créent une vraie base SQLite avec Django et la copient vers un PostgreSQL 17 jetable ; `test_e2e_sqlite.py` lance l'exécutable en mode SQLite (sans Docker). Les tests e2e lancent l'exécutable figé contre un PostgreSQL 17 jetable (Docker, port 55432) ; sans Docker ils sont ignorés. Les tests de l'interface Tk pilotent les vrais widgets hors écran. Tous les tests utilisent `TJ_DATA_DIR` : ils ne touchent jamais aux vraies données.

## Commandes de maintenance (`tjctl.exe`)

`self-test`, `status`, `backup <fichier>`, `verify <fichier>`, `restore <fichier>` (refusée si l'application tourne ; une sauvegarde de sécurité « avant-restauration-… » est créée avant).

## Sécurité

- Écoute exclusivement sur `127.0.0.1` ; en-têtes de sécurité ; cookies HttpOnly, noms propres à l'application (`tj_sessionid`, `tj_csrftoken`).
- Création de compte : refusée dès qu'un en-tête de redirection (`X-Forwarded-*`, `Forwarded`) signale une origine distante ; limitée à 10 tentatives/heure.
- Mots de passe PostgreSQL jamais en ligne de commande (stdin, `PGPASSWORD` ou fichier d'options temporaire).
- Archives de sauvegarde : empreinte vérifiée, entrées dangereuses (`../`, chemins absolus, lecteurs) refusées avant toute écriture.
- Audit des dépendances : `pip-audit` sans vulnérabilité connue ; `npm audit --omit=dev` signale 6 alertes (2 faibles, 4 modérées) uniquement dans l'outillage de build (`shadcn` → `deepmerge`, `ts-morph` → `minimatch`) ; ces paquets **ne sont pas** dans l'application livrée (vérifié dans `dist`).

## Limites connues

- L'installateur PostgreSQL (chemin UAC réel) est couvert par des tests unitaires et par la documentation EDB, mais **n'a pas été exécuté** sur une machine propre : à valider sur un poste vierge avant diffusion.
- Exécutable non signé : SmartScreen/antivirus peuvent afficher un avertissement (« Informations complémentaires › Exécuter quand même »). Une signature de code l'évite.
- L'interface Tk est testée par automatisation des widgets, pas par inspection visuelle.
- Windows uniquement ; mise à jour = réinstaller par-dessus (migrations appliquées au démarrage).
