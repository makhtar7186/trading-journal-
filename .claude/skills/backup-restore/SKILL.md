---
name: backup-restore
description: Procédure de sauvegarde et restauration du Trading Journal (PostgreSQL + dossier de captures), avec test de restauration. À utiliser pour la documentation docs/deployment.md, la phase 8 ou avant toute opération risquée sur les données.
---

# Sauvegarde & restauration

Deux éléments à sauvegarder **ensemble** (cohérence base ↔ fichiers) :
1. Base PostgreSQL.
2. Captures (`storage/` en dev ; bucket S3 en prod, avec versioning activé).

## Sauvegarde (exemples à adapter aux noms réels du Compose)
```bash
# Base (format custom, restaurable avec pg_restore)
docker compose exec -T db pg_dump -U "$POSTGRES_USER" -Fc "$POSTGRES_DB" > backups/db_$(date +%F_%H%M).dump
# Captures locales
tar -czf backups/storage_$(date +%F_%H%M).tar.gz storage/
```
Sur Windows/PowerShell, adapter la redirection (`cmd /c` ou `--file` dans le conteneur puis `docker cp`) pour éviter la corruption d'encodage du dump.

## Restauration
```bash
docker compose exec -T db pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists < backups/db_YYYY-MM-DD_HHMM.dump
tar -xzf backups/storage_YYYY-MM-DD_HHMM.tar.gz
docker compose restart backend
```

## Règles
- Dossier `backups/` dans `.gitignore` ; copie hors machine (chiffrée si possible).
- Rotation/rétention documentée (ex. quotidiennes 7 j, hebdomadaires 4 sem.).
- **Tester la restauration** sur un environnement vierge (critère d'acceptation n°10) : trades, stratégies et captures doivent réapparaître et les images s'afficher.
- Ne jamais lancer une restauration `--clean` sur la prod sans sauvegarde préalable ni confirmation de l'utilisateur.
- Documenter la procédure dans `docs/deployment.md` et le README.
