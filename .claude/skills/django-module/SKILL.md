---
name: django-module
description: Recette pour créer ou étendre un module backend Django/DRF du Trading Journal (modèle, migration, service, selector, serializer, vue, URL, tests) avec isolation par utilisateur. À utiliser pour toute nouvelle ressource API.
---

# Module backend Django/DRF

Chaque module vit dans `backend/apps/<module>/` :

```
models.py        # modèles + contraintes + index
services.py      # (ou services/) opérations métier qui écrivent, en transaction
selectors.py     # lectures complexes / agrégations (léger, seulement si utile)
serializers.py   # validation de forme ; pas de règle métier lourde
views.py         # vues fines (ViewSet / APIView)
urls.py
filters.py       # django-filter si pertinent
admin.py
migrations/
tests/           # ou backend/tests/<module>/
```

## Règles
1. **UUID** en clé primaire (`default=uuid.uuid4, editable=False`).
2. **Propriétaire** : `user = ForeignKey(settings.AUTH_USER_MODEL, on_delete=CASCADE)`. Le serializer **n'accepte pas** `user` ; la vue/le service l'assigne depuis `request.user`.
3. **Queryset** : `get_queryset()` filtre toujours `user=self.request.user`. Ressource d'autrui → 404.
   Pour une ressource enfant (capture), filtrer via `trade__user`.
4. **Vues fines** : validation → appel d'un service → sérialisation. Pas de calcul métier dans la vue.
5. **Services** : fonctions explicites (`create_trade`, `close_trade`, …) décorées `@transaction.atomic` quand plusieurs écritures ; lèvent des exceptions métier mappées en 400/409 par un handler central (`core/`).
6. **Contraintes DB** (`CheckConstraint`, `UniqueConstraint`) en plus de la validation applicative ; **index** sur champs filtrés (`user`, `trade_date`, `status`, `market_type`, `asset`, `strategy`).
7. **Pagination, tri, recherche, filtres** côté serveur (`PageNumberPagination`, `OrderingFilter`, `SearchFilter`, `django-filter`).
8. **Documentation** OpenAPI avec `drf-spectacular` (`extend_schema`) : paramètres, réponses, erreurs.
9. **Migrations** versionnées, relues, jamais éditées après application ailleurs.
10. Pas de `float` pour l'argent/RR ; `Decimal` uniquement.

## Checklist avant de livrer
- [ ] `python manage.py makemigrations --check` propre
- [ ] Tests : création / lecture / modification / suppression
- [ ] Test d'isolation : l'utilisateur B reçoit 404 sur les ressources de A (GET, PATCH, DELETE)
- [ ] Test de non-confiance : `user` envoyé par le client est ignoré
- [ ] Schéma OpenAPI généré sans warning
- [ ] Voir `trading-domain-rules` pour tout ce qui touche statuts/RR
