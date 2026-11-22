"""Création d'un compte pour le lanceur desktop.

Les données arrivent en JSON sur l'ENTRÉE STANDARD (jamais en argument : un mot de passe en ligne de commande
est visible dans la liste des processus). Sortie : une ligne JSON ; code 0 si créé, 2 si refusé.
"""
import json
import sys

from django.core.management.base import BaseCommand

from apps.accounts.registration import AccountCreationError, create_account
from apps.accounts.serializers import RegisterSerializer


class Command(BaseCommand):
    help = "Crée un compte ordinaire. Entrée : JSON {username, password, email?, timezone?} sur stdin."

    def handle(self, *args, **options):
        try:
            payload = json.loads(sys.stdin.read() or "{}")
        except json.JSONDecodeError:
            self._fail({"detail": ["Entrée JSON invalide."]})
        if not isinstance(payload, dict):
            self._fail({"detail": ["Entrée JSON invalide."]})

        payload.setdefault("password_confirm", payload.get("password"))  # la confirmation est faite par l'appelant
        serializer = RegisterSerializer(data=payload)
        if not serializer.is_valid():
            self._fail({field: [str(m) for m in messages] for field, messages in serializer.errors.items()})
        data = serializer.validated_data
        try:
            user = create_account(
                username=data["username"], password=data["password"], email=data["email"], timezone=data["timezone"]
            )
        except AccountCreationError as exc:
            self._fail(exc.errors)
        self.stdout.write(json.dumps({"ok": True, "username": user.username}))

    def _fail(self, errors):
        self.stdout.write(json.dumps({"ok": False, "errors": errors}))
        raise SystemExit(2)
