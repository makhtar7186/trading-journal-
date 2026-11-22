"""Configuration persistante (config.json dans le dossier de données). Les secrets sont chiffrés (DPAPI)."""
from __future__ import annotations

import json
import os
import secrets
from dataclasses import asdict, dataclass, field
from pathlib import Path

from . import paths, secrets_store

CONFIG_VERSION = 1
DEFAULT_UI_PORT = 47300
DEFAULT_API_PORT = 47301
ENGINE_POSTGRES = "postgres"
ENGINE_SQLITE = "sqlite"  # mode de secours : PostgreSQL n'a pas pu être configuré
SECRET_FIELDS = ("password", "superuser_password")


@dataclass
class PostgresConfig:
    host: str = "127.0.0.1"
    port: int = 5432
    database: str = "trading_journal"
    user: str = "trading_journal"
    password: str = ""  # mot de passe du rôle applicatif (jamais superutilisateur)
    bin_dir: str = ""  # dossier contenant pg_dump / pg_restore / pg_isready
    service: str = ""  # nom du service Windows (pour le démarrer s'il est arrêté)
    managed: bool = False  # True si NOUS avons installé ce PostgreSQL
    superuser_password: str = ""  # uniquement si managed (jamais demandé à l'utilisateur dans ce cas)


@dataclass
class Config:
    version: int = CONFIG_VERSION
    ui_port: int = DEFAULT_UI_PORT
    api_port: int = DEFAULT_API_PORT
    secret_key: str = ""
    postgres: PostgresConfig = field(default_factory=PostgresConfig)
    last_app_version: str = ""
    db_engine: str = ENGINE_POSTGRES
    fallback_reason: str = ""  # pourquoi SQLite est utilisé (affiché à l'utilisateur)
    upgrade_snooze_until: str = ""  # ISO : pas de nouvelle proposition de migration avant cette date

    @property
    def uses_sqlite(self) -> bool:
        return self.db_engine == ENGINE_SQLITE

    @property
    def configured(self) -> bool:
        if not self.secret_key:
            return False
        return True if self.uses_sqlite else bool(self.postgres.password)

    @property
    def ui_url(self) -> str:
        # 127.0.0.1 et non « localhost » : les cookies sont isolés par hôte, pas par port, donc on évite de partager
        # la session avec d'autres applications locales.
        return f"http://127.0.0.1:{self.ui_port}"

    @property
    def api_url(self) -> str:
        return f"http://127.0.0.1:{self.api_port}"

    def new_secret_key(self) -> None:
        self.secret_key = secrets.token_urlsafe(64)


def _encode(config: Config) -> dict:
    data = asdict(config)
    data["secret_key"] = secrets_store.protect(config.secret_key) if config.secret_key else ""
    for name in SECRET_FIELDS:
        value = data["postgres"][name]
        data["postgres"][name] = secrets_store.protect(value) if value else ""
    return data


def _decode(data: dict) -> Config:
    pg_raw = dict(data.get("postgres") or {})
    for name in SECRET_FIELDS:
        token = pg_raw.get(name) or ""
        pg_raw[name] = secrets_store.unprotect(token) if token else ""
    known = {k: v for k, v in pg_raw.items() if k in PostgresConfig.__dataclass_fields__}
    secret = data.get("secret_key") or ""
    return Config(
        version=int(data.get("version", CONFIG_VERSION)),
        ui_port=int(data.get("ui_port", DEFAULT_UI_PORT)),
        api_port=int(data.get("api_port", DEFAULT_API_PORT)),
        secret_key=secrets_store.unprotect(secret) if secret else "",
        postgres=PostgresConfig(**known),
        last_app_version=str(data.get("last_app_version", "")),
        db_engine=data.get("db_engine") if data.get("db_engine") in (ENGINE_POSTGRES, ENGINE_SQLITE) else ENGINE_POSTGRES,
        fallback_reason=str(data.get("fallback_reason", "")),
        upgrade_snooze_until=str(data.get("upgrade_snooze_until", "")),
    )


def load(path: Path | None = None) -> Config:
    """Charge la configuration ; une configuration absente ou illisible donne une configuration vierge
    (le lanceur refait alors l'assistant, sans jamais supprimer la base de données existante)."""
    path = path or paths.config_path()
    try:
        return _decode(json.loads(path.read_text(encoding="utf-8")))
    except (FileNotFoundError, json.JSONDecodeError, ValueError, OSError):
        return Config()


def save(config: Config, path: Path | None = None) -> None:
    """Écriture atomique (fichier temporaire puis remplacement) : jamais de configuration à moitié écrite."""
    path = path or paths.config_path()
    payload = json.dumps(_encode(config), indent=2, ensure_ascii=False)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(payload, encoding="utf-8")
    os.replace(tmp, path)
