"""Emplacements : l'installation est en lecture seule ; les données vivent dans %LOCALAPPDATA%."""
import os
import sys
from pathlib import Path

from .version import APP_ID

_REPO_DESKTOP = Path(__file__).resolve().parents[1]  # desktop/ (mode développement)


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def app_dir() -> Path:
    """Dossier de l'installation (là où se trouve l'exécutable)."""
    return Path(sys.executable).resolve().parent if is_frozen() else _REPO_DESKTOP


def bundle_dir() -> Path:
    """Ressources embarquées par PyInstaller (ou desktop/ en développement)."""
    return Path(getattr(sys, "_MEIPASS", _REPO_DESKTOP))


def data_dir() -> Path:
    """Données modifiables : configuration, journaux, captures, sauvegardes. JAMAIS à côté de l'exécutable."""
    override = os.environ.get("TJ_DATA_DIR")
    base = Path(override) if override else Path(os.environ.get("LOCALAPPDATA", Path.home())) / APP_ID
    base.mkdir(parents=True, exist_ok=True)
    return base


def config_path() -> Path:
    return data_dir() / "config.json"


def logs_dir() -> Path:
    d = data_dir() / "logs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def storage_dir() -> Path:
    d = data_dir() / "storage"
    d.mkdir(parents=True, exist_ok=True)
    return d


def sqlite_path() -> Path:
    """Base SQLite du mode de secours."""
    return data_dir() / "trading_journal.sqlite3"


def backups_dir() -> Path:
    d = data_dir() / "backups"
    d.mkdir(parents=True, exist_ok=True)
    return d


def downloads_dir() -> Path:
    d = data_dir() / "downloads"
    d.mkdir(parents=True, exist_ok=True)
    return d


def backend_dir() -> Path:
    """Code Django : embarqué dans l'exécutable, ou dossier backend/ du dépôt en développement."""
    return bundle_dir() if is_frozen() else _REPO_DESKTOP.parent / "backend"


def frontend_dir() -> Path:
    """Build Next.js « standalone » (contient server.js)."""
    override = os.environ.get("TJ_FRONTEND_DIR")
    if override:
        return Path(override)
    return app_dir() / "frontend" if is_frozen() else _REPO_DESKTOP / "build" / "frontend"


def node_exe() -> Path:
    override = os.environ.get("TJ_NODE")
    if override:
        return Path(override)
    return app_dir() / "node" / "node.exe" if is_frozen() else Path(os.environ.get("NODE_EXE", "node"))


def cli_exe() -> list[str]:
    """Commande pour relancer ce programme (sous-commandes serve-api, manage…)."""
    if is_frozen():
        cli = app_dir() / "tjctl.exe"
        return [str(cli if cli.exists() else sys.executable)]
    return [sys.executable, "-m", "tjlauncher"]
