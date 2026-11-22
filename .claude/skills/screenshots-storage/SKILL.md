---
name: screenshots-storage
description: Gestion des captures d'écran de trades — modèle TradeScreenshot, abstraction de stockage local/S3, upload sécurisé, accès privé, galerie et upload multiple côté frontend. À utiliser pour la phase 5 ou tout code touchant aux images.
---

# Captures d'écran

> **État : implémenté (phase 5).** Code : `backend/core/storage/`, `backend/apps/screenshots/` (`images.py` = validation/ré-encodage, `services.py` = tout-ou-rien, `signals.py` = nettoyage `on_commit`), `frontend/src/features/screenshots/`. Écarts par rapport au plan ci-dessous : liste non paginée ; un fichier par requête côté frontend (erreurs par fichier) mais l'API accepte plusieurs fichiers (tout-ou-rien) ; S3 redirige (302) vers une URL signée de 60 s, le stockage local streame via Django. Voir aussi « Pièges connus » dans CLAUDE.md.

## Modèle
`TradeScreenshot` : `id` UUID, `trade` FK obligatoire (CASCADE), `storage_key`, `original_filename`, `category` (`BEFORE|DURING|AFTER`), `description` (facultative), `uploaded_at`. **Aucun binaire en base.**

## Abstraction de stockage
- Interface minimale dans `core/storage/` : `save(key, file) -> key`, `open(key)`, `delete(key)`, `url(key, expires)`.
- Implémentations : `LocalStorage` (dossier `storage/`, dev) et `S3Storage` (boto3/`django-storages`, prod). Choix par variable d'environnement. Le code métier ne dépend d'aucun fournisseur.
- Clé de stockage : générée serveur, aléatoire, ex. `trades/<trade_uuid>/<uuid4>.<ext_sûre>`. Jamais le nom client.

## Upload sécurisé (backend)
Valider **avant** d'enregistrer :
1. Taille max configurable (`SCREENSHOT_MAX_BYTES`), aussi côté reverse proxy.
2. Type **réel** par magic bytes (Pillow `Image.open().verify()` ou `python-magic`) — pas seulement `Content-Type`/extension.
3. Whitelist : `image/png`, `image/jpeg`, `image/webp` (SVG refusé : risque XSS).
4. Ré-encoder/normaliser l'image si possible (supprime EXIF/GPS et payloads cachés) ; limiter les dimensions (anti decompression bomb : `Image.MAX_IMAGE_PIXELS`).
5. Nom d'origine conservé seulement comme métadonnée, assaini.
6. Transaction : si l'écriture en DB échoue, supprimer le fichier ; si le fichier échoue, ne rien créer. Suppression d'un trade → supprimer ses fichiers.
7. Vérifier que le trade appartient à `request.user`.

## Accès privé
- Aucun `MEDIA_URL` public. Endpoint authentifié qui contrôle `screenshot.trade.user == request.user` puis streame le fichier (`Content-Type` fixé, `X-Content-Type-Options: nosniff`, `Content-Disposition` approprié), ou URL signée de courte durée en S3.
- 404 pour une capture d'autrui.

## API
`GET/POST /trades/{id}/screenshots/` (POST multi-fichiers, `multipart/form-data`) · `PATCH/DELETE /screenshots/{id}/`.

## Frontend (`features/screenshots/`)
Sélection multiple, prévisualisation locale (`URL.createObjectURL`, à révoquer), catégorie par fichier, **progression réelle** (XHR/axios `onUploadProgress`), galerie par trade filtrable par catégorie, vue agrandie (modale accessible, flèches clavier, Échap), édition catégorie/description, suppression avec confirmation. Gérer erreurs par fichier (type/taille refusés).

## Tests
Upload valide · faux PNG (contenu non-image) refusé · trop gros refusé · extension trompeuse · accès par un autre utilisateur = 404 · suppression nettoie le fichier · rollback en cas d'échec · taille/formats configurables.
