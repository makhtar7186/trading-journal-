"""Interface utilisateur abstraite du lanceur : l'assistant graphique (Tk) et le mode sans fenêtre l'implémentent."""
from __future__ import annotations

from collections.abc import Callable
from typing import Protocol


class SetupCancelled(Exception):
    """L'utilisateur a annulé l'assistant."""


class UI(Protocol):
    def status(self, text: str) -> None: ...

    def progress(self, fraction: float | None) -> None:
        """0..1, ou None pour une progression indéterminée."""

    def confirm(self, title: str, message: str) -> bool: ...

    def choose(self, title: str, message: str, options: list[str]) -> int | None:
        """Retourne l'index choisi, ou None si annulé."""

    def ask_secret(self, title: str, message: str, error: str | None = None) -> str | None: ...

    def ask_connection(self) -> dict | None:
        """Paramètres d'un PostgreSQL existant : {host, port, user, password}, ou None si annulé."""

    def account_dialog(self, create: Callable[[dict], dict]) -> bool:
        """Propose de créer un compte. `create(valeurs)` retourne {"ok": True} ou {"ok": False, "errors": {...}} ;
        le dialogue affiche les erreurs et laisse corriger. Retourne True si un compte a été créé."""

    def error(self, title: str, message: str) -> None: ...


class HeadlessUI:
    """Sans fenêtre : réponses préenregistrées (tests, automatisation) ; sinon refus prudent."""

    def __init__(self, *, confirm: bool = True, choice: int | None = 0, secret: str | None = None, connection: dict | None = None,
                 account: dict | None = None, log: Callable[[str], None] | None = None):
        self._account = account
        self._confirm, self._choice, self._secret, self._connection = confirm, choice, secret, connection
        self._log = log or (lambda text: None)
        self.messages: list[str] = []
        self.errors: list[str] = []

    def status(self, text: str) -> None:
        self.messages.append(text)
        self._log(text)

    def progress(self, fraction: float | None) -> None:
        return None

    def confirm(self, title: str, message: str) -> bool:
        self._log(f"[confirmation] {title}: {message} -> {self._confirm}")
        return self._confirm

    def choose(self, title: str, message: str, options: list[str]) -> int | None:
        self._log(f"[choix] {title}: {message} -> {self._choice}")
        return self._choice

    def ask_secret(self, title: str, message: str, error: str | None = None) -> str | None:
        return self._secret if error is None else None  # une 2e demande signifie que la réponse était fausse

    def ask_connection(self) -> dict | None:
        return self._connection

    def account_dialog(self, create: Callable[[dict], dict]) -> bool:
        if not self._account:
            return False
        result = create(self._account)
        if not result.get("ok"):
            self.errors.append(f"Compte refusé : {result.get('errors')}")
            self._log(f"[erreur] Création du compte refusée : {result.get('errors')}")
        else:
            self._log(f"Compte « {result.get('username', '')} » créé.")
        return bool(result.get("ok"))

    def error(self, title: str, message: str) -> None:
        self.errors.append(f"{title}: {message}")
        self._log(f"[erreur] {title}: {message}")
