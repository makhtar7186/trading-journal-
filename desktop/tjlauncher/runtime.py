"""Exécution du backend : environnement, commandes de gestion Django (migrations, comptes)."""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from . import paths
from .config import Config

CREATE_NO_WINDOW = 0x08000000
_STRIPPED_PREFIXES = ("DJANGO_", "DB_ENGINE", "SQLITE_", "POSTGRES_", "API_", "CSRF_", "CORS_", "STORAGE_", "S3_", "SCREENSHOT_", "ALLOW_REGISTRATION", "LOG_DIR")


def backend_env(cfg: Config, base: dict | None = None) -> dict:
    """Variables d'environnement du backend. On part de l'environnement courant SANS les réglages Django/PostgreSQL
    éventuellement hérités (ex. d'un poste de développement) : seule notre configuration fait foi."""
    env = {k: v for k, v in (base if base is not None else os.environ).items() if not k.startswith(_STRIPPED_PREFIXES)}
    pg = cfg.postgres
    env.update(
        {
            "DJANGO_SETTINGS_MODULE": "config.settings.desktop",
            "DJANGO_SECRET_KEY": cfg.secret_key,
            "DB_ENGINE": cfg.db_engine,
            "SQLITE_PATH": str(paths.sqlite_path()),
            "POSTGRES_DB": pg.database,
            "POSTGRES_USER": pg.user,
            "POSTGRES_PASSWORD": pg.password,
            "POSTGRES_HOST": pg.host,
            "POSTGRES_PORT": str(pg.port),
            "API_HOST": "127.0.0.1",
            "API_PORT": str(cfg.api_port),
            "CSRF_TRUSTED_ORIGINS": f"http://127.0.0.1:{cfg.ui_port},http://localhost:{cfg.ui_port}",
            "LOG_DIR": str(paths.logs_dir()),
            "STORAGE_BACKEND": "local",
            "STORAGE_LOCAL_ROOT": str(paths.storage_dir()),
            "ALLOW_REGISTRATION": "true",
            "PYTHONUTF8": "1",
            "PYTHONIOENCODING": "utf-8",
        }
    )
    if not paths.is_frozen():
        env["PYTHONPATH"] = os.pathsep.join([str(paths.backend_dir()), str(Path(__file__).resolve().parents[1])])
    return env


class ManageError(Exception):
    pass


def run_manage(cfg: Config, args: list[str], *, stdin: str | None = None, timeout: float = 600, run=subprocess.run) -> subprocess.CompletedProcess:
    """`manage.py <args>` dans un processus séparé (même exécutable). Le mot de passe passe par stdin, jamais en argument."""
    command = [*paths.cli_exe(), "manage", *args]
    return run(command, input=stdin, capture_output=True, text=True, encoding="utf-8", timeout=timeout,
               env=backend_env(cfg), cwd=str(paths.backend_dir() if not paths.is_frozen() else paths.app_dir()),
               creationflags=CREATE_NO_WINDOW)


def migrate(cfg: Config, run=subprocess.run) -> None:
    result = run_manage(cfg, ["migrate", "--noinput"], run=run)
    if result.returncode != 0:
        tail = (result.stderr or result.stdout or "").strip().splitlines()[-8:]
        raise ManageError("Les migrations de la base ont échoué :\n" + "\n".join(tail))


def count_users(cfg: Config, run=subprocess.run) -> int:
    result = run_manage(cfg, ["count_users"], run=run)
    if result.returncode != 0:
        raise ManageError("Impossible de lire les comptes : " + (result.stderr or "").strip()[-300:])
    return int((result.stdout or "0").strip().splitlines()[-1])


def create_account(cfg: Config, *, username: str, password: str, email: str = "", timezone: str = "UTC", run=subprocess.run) -> dict:
    """Crée un compte ordinaire. Retourne {"ok": True, ...} ou {"ok": False, "errors": {champ: [messages]}}."""
    payload = json.dumps({"username": username, "password": password, "email": email, "timezone": timezone})
    result = run_manage(cfg, ["register_user"], stdin=payload, run=run)
    lines = (result.stdout or "").strip().splitlines()
    try:
        return json.loads(lines[-1])
    except (IndexError, json.JSONDecodeError):
        return {"ok": False, "errors": {"detail": ["Création impossible : " + ((result.stderr or "").strip()[-200:] or "réponse illisible")]}}


# -- migration de données entre moteurs (SQLite -> PostgreSQL) ---------------------------------------------------------
# Tables hors périmètre : types de contenu et permissions (recréés par `migrate`), sessions (l'utilisateur se reconnecte).
DUMP_EXCLUDES = ("contenttypes", "auth.permission", "sessions", "admin.logentry")


def row_counts(cfg: Config, run=subprocess.run) -> dict[str, int]:
    result = run_manage(cfg, ["count_rows"], run=run)
    if result.returncode != 0:
        raise ManageError("Impossible de compter les données : " + (result.stderr or "").strip()[-300:])
    try:
        return json.loads((result.stdout or "").strip().splitlines()[-1])
    except (IndexError, json.JSONDecodeError) as exc:
        raise ManageError("Réponse illisible du décompte des données.") from exc


def dump_data(cfg: Config, dest: Path, run=subprocess.run) -> None:
    args = ["dumpdata", "--natural-foreign", "--output", str(dest)]
    for label in DUMP_EXCLUDES:
        args += ["--exclude", label]
    result = run_manage(cfg, args, run=run)
    if result.returncode != 0 or not dest.exists():
        raise ManageError("L'export des données a échoué : " + (result.stderr or "").strip()[-300:])


def load_data(cfg: Config, src: Path, run=subprocess.run) -> None:
    result = run_manage(cfg, ["loaddata", str(src)], run=run)  # une seule transaction : tout ou rien
    if result.returncode != 0:
        raise ManageError("L'import des données a échoué : " + (result.stderr or "").strip()[-300:])


def flush(cfg: Config, run=subprocess.run) -> None:
    """Vide la base cible. Réservé à une base que NOUS venons de remplir (jamais à des données préexistantes)."""
    result = run_manage(cfg, ["flush", "--noinput"], run=run)
    if result.returncode != 0:
        raise ManageError("Impossible de vider la base après l'échec : " + (result.stderr or "").strip()[-300:])
