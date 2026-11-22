"""Création de compte : règles d'accès et service.

La création de compte depuis l'interface est un choix propre à la version desktop (un seul poste,
serveur lié à 127.0.0.1). Elle reste DÉSACTIVÉE par défaut et n'est acceptée que pour des requêtes
venant de la machine elle-même : une exposition accidentelle du serveur ne doit jamais ouvrir l'inscription.
"""
import ipaddress
import re

from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction

from .models import User

# En-têtes par lesquels un relais (reverse proxy, tunnel…) indique l'origine réelle d'une requête.
# HTTP_X_TJ_FORWARDED est posé par src/proxy.ts du frontend : copie de ce que le CLIENT a envoyé, avant que le
# serveur Next ne réécrive X-Forwarded-For (sans cela, un en-tête falsifié derrière un relais serait invisible).
FORWARDING_HEADERS = ("HTTP_X_FORWARDED_FOR", "HTTP_FORWARDED", "HTTP_X_REAL_IP", "HTTP_X_TJ_FORWARDED")
_SPLIT = re.compile(r"[,;\s=]+")
_KEYWORDS = ("for", "by", "host", "proto", "http", "https")


class AccountCreationError(Exception):
    """Échec de création ; `errors` : {champ: [messages]}."""

    def __init__(self, errors: dict[str, list[str]]):
        self.errors = errors
        super().__init__("; ".join(f"{k}: {' '.join(v)}" for k, v in errors.items()))


def _parse_ip(token: str):
    token = token.strip().strip('"')
    bracket = re.match(r"^\[(.*)\](:\d+)?$", token)  # [::1] ou [::1]:8080
    if bracket:
        token = bracket.group(1)
    elif token.count(":") == 1 and "." in token:  # 127.0.0.1:8080
        token = token.split(":")[0]
    try:
        address = ipaddress.ip_address(token)
    except ValueError:
        return None
    if address.version == 6 and address.ipv4_mapped is not None:  # ::ffff:127.0.0.1 = 127.0.0.1
        address = address.ipv4_mapped
    return address


def _is_loopback(value: str) -> bool:
    address = _parse_ip(value)
    return address is not None and address.is_loopback


def _header_is_local(value: str) -> bool:
    """Vrai si l'en-tête ne désigne QUE des adresses de la machine. Un en-tête sans aucune adresse lisible
    (nom masqué, valeur illisible) est refusé : dans le doute, ce n'est pas local."""
    seen = False
    for raw in _SPLIT.split(value):
        token = raw.strip()
        if not token or token.lower() in _KEYWORDS:
            continue
        address = _parse_ip(token)
        if address is None:
            return False  # nom d'hôte, « _hidden », valeur illisible…
        seen = True
        if not address.is_loopback:
            return False
    return seen


def is_loopback_request(request) -> bool:
    """Vrai uniquement si la connexion ET toute indication de relais proviennent de la machine locale."""
    if not _is_loopback(request.META.get("REMOTE_ADDR", "")):
        return False
    for name in FORWARDING_HEADERS:
        value = request.META.get(name, "")
        if value.strip() and not _header_is_local(value):
            return False
    return True


def registration_enabled(request) -> bool:
    return bool(settings.ALLOW_REGISTRATION) and is_loopback_request(request)


def create_account(*, username: str, password: str, email: str = "", timezone: str = "UTC") -> User:
    """Crée un utilisateur ordinaire (ni staff ni superuser). Valide le mot de passe avec les validateurs Django."""
    candidate = User(username=username, email=email)
    try:
        validate_password(password, user=candidate)
    except DjangoValidationError as exc:
        raise AccountCreationError({"password": list(exc.messages)}) from exc
    try:
        with transaction.atomic():
            return User.objects.create_user(username=username, email=email, password=password, timezone=timezone)
    except IntegrityError as exc:  # course entre deux créations simultanées
        raise AccountCreationError({"username": ["Cet identifiant est déjà utilisé."]}) from exc
