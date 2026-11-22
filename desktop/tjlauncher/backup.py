"""Sauvegarde et restauration : base PostgreSQL + captures d'écran, dans UN SEUL fichier .tjbackup (zip).

Contenu : manifest.json (version, date, moteur, empreinte de la base), db.dump (pg_dump -Fc) ou db.sqlite3 (mode de secours
SQLite), storage/ (captures).
Les mots de passe passent par la variable PGPASSWORD (jamais en argument de commande).
"""
from __future__ import annotations

import hashlib
import json
import os
import secrets
import shutil
import sqlite3
import subprocess
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from . import paths
from .config import Config
from .version import __version__

EXTENSION = ".tjbackup"
MANIFEST = "manifest.json"
DUMP = "db.dump"
SQLITE_DUMP = "db.sqlite3"
STORAGE_PREFIX = "storage/"
CREATE_NO_WINDOW = 0x08000000


class BackupError(Exception):
    """Erreur affichable à l'utilisateur."""


def pg_tool(cfg: Config, name: str) -> str:
    candidates = []
    if cfg.postgres.bin_dir:
        candidates.append(Path(cfg.postgres.bin_dir) / f"{name}.exe")
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    found = shutil.which(name)
    if found:
        return found
    raise BackupError(f"Outil PostgreSQL « {name} » introuvable. Réinstallez PostgreSQL avec les outils en ligne de commande.")


def _env(cfg: Config) -> dict:
    env = dict(os.environ)
    env["PGPASSWORD"] = cfg.postgres.password
    return env


def _pg_args(cfg: Config) -> list[str]:
    pg = cfg.postgres
    return ["-h", pg.host, "-p", str(pg.port), "-U", pg.user]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def db_member(engine: str) -> str:
    """Nom du fichier de base dans l'archive, selon le moteur."""
    return SQLITE_DUMP if engine == "sqlite" else DUMP


def _sqlite_snapshot(source: Path, dest: Path) -> None:
    """Copie cohérente d'une base SQLite même ouverte par l'application (API de sauvegarde en ligne de SQLite)."""
    if not source.exists():
        raise BackupError("La base de données SQLite est introuvable.")
    src = sqlite3.connect(f"file:{source.as_posix()}?mode=ro", uri=True, timeout=30)
    try:
        dst = sqlite3.connect(dest)
        try:
            src.backup(dst)
        finally:
            dst.close()
    except sqlite3.Error as exc:
        raise BackupError(f"La sauvegarde de la base SQLite a échoué : {exc}") from exc
    finally:
        src.close()


def default_name(prefix: str = "") -> str:
    # Suffixe aléatoire : deux sauvegardes créées dans la même seconde ne portent jamais le même nom.
    return f"{prefix}trading-journal-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{secrets.token_hex(2)}{EXTENSION}"


def create_backup(cfg: Config, dest: Path, *, run=subprocess.run, storage: Path | None = None, sqlite_path: Path | None = None) -> Path:
    """Crée la sauvegarde de façon atomique (fichier temporaire puis renommage) et retourne son chemin."""
    storage = storage if storage is not None else paths.storage_dir()
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=dest.parent) as tmp_name:
        tmp = Path(tmp_name)
        engine = "sqlite" if cfg.uses_sqlite else "postgres"
        dump = tmp / db_member(engine)
        if cfg.uses_sqlite:
            _sqlite_snapshot(sqlite_path or paths.sqlite_path(), dump)
        else:
            result = run(
                [pg_tool(cfg, "pg_dump"), *_pg_args(cfg), "-d", cfg.postgres.database, "-Fc", "--no-owner", "--no-privileges", "-f", str(dump)],
                env=_env(cfg), capture_output=True, text=True, creationflags=CREATE_NO_WINDOW,
            )
            if result.returncode != 0 or not dump.exists():
                raise BackupError("La sauvegarde de la base a échoué : " + (result.stderr or "").strip()[-300:])

        files = [p for p in storage.rglob("*") if p.is_file()] if storage.exists() else []
        manifest = {
            "format": 1,
            "app_version": __version__,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "engine": engine,
            "database": cfg.postgres.database if engine == "postgres" else SQLITE_DUMP,
            "db_sha256": _sha256(dump),
            "db_bytes": dump.stat().st_size,
            "storage_files": len(files),
        }
        partial = tmp / "backup.partial"
        with zipfile.ZipFile(partial, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(MANIFEST, json.dumps(manifest, indent=2))
            archive.write(dump, db_member(engine))
            for file in files:
                archive.write(file, STORAGE_PREFIX + file.relative_to(storage).as_posix())
        os.replace(partial, dest)
    return dest


def read_manifest(archive: zipfile.ZipFile) -> dict:
    try:
        manifest = json.loads(archive.read(MANIFEST))
    except (KeyError, json.JSONDecodeError) as exc:
        raise BackupError("Ce fichier n'est pas une sauvegarde Trading Journal valide.") from exc
    if manifest.get("format") != 1 or db_member(manifest.get("engine", "postgres")) not in archive.namelist():
        raise BackupError("Sauvegarde incompatible ou incomplète.")
    return manifest


def _safe_target(root: Path, name: str) -> Path:
    """Chemin de destination d'une entrée d'archive ; refuse toute évasion (zip slip : « .. », chemins absolus)."""
    target = (root / name).resolve()
    if root.resolve() not in target.parents:
        raise BackupError(f"Entrée d'archive dangereuse refusée : {name}")
    return target


def _unsafe_entry(name: str) -> bool:
    """Entrée de captures dangereuse : chemin absolu, lecteur, « .. » ou composant vide (storage//x)."""
    rest = name[len(STORAGE_PREFIX):]
    parts = rest.replace("\\", "/").split("/")
    return (not rest) or rest.startswith(("/", "\\")) or ":" in rest or ".." in parts or (len(parts) > 1 and "" in parts[:-1])


def verify_backup(path: Path) -> dict:
    """Contrôle l'intégrité (zip valide, manifeste, empreinte de la base) sans rien restaurer."""
    try:
        with zipfile.ZipFile(path) as archive:
            manifest = read_manifest(archive)
            if archive.testzip() is not None:
                raise BackupError("Sauvegarde corrompue (archive endommagée).")
            digest = hashlib.sha256()
            with archive.open(db_member(manifest.get("engine", "postgres"))) as handle:
                for block in iter(lambda: handle.read(1 << 20), b""):
                    digest.update(block)
            if digest.hexdigest() != manifest.get("db_sha256"):
                raise BackupError("Sauvegarde corrompue (empreinte de la base différente).")
            for name in archive.namelist():
                if name.startswith(STORAGE_PREFIX) and not name.endswith("/") and _unsafe_entry(name):
                    raise BackupError(f"Entrée d'archive dangereuse refusée : {name}")
            return manifest
    except zipfile.BadZipFile as exc:
        raise BackupError("Ce fichier n'est pas une sauvegarde valide.") from exc


def restore_backup(cfg: Config, src: Path, *, run=subprocess.run, storage: Path | None = None, backups: Path | None = None,
                   sqlite_path: Path | None = None) -> Path:
    """Restaure base ET captures. L'application doit être ARRÊTÉE. Retourne le chemin de la sauvegarde de sécurité
    créée juste avant (l'état précédent reste donc récupérable)."""
    storage = storage if storage is not None else paths.storage_dir()
    backups = backups if backups is not None else paths.backups_dir()
    manifest = verify_backup(src)  # avant toute modification
    engine = manifest.get("engine", "postgres")
    current = "sqlite" if cfg.uses_sqlite else "postgres"
    if engine != current:
        names = {"sqlite": "SQLite (mode de secours)", "postgres": "PostgreSQL"}
        raise BackupError(f"Cette sauvegarde provient d'une base {names[engine]} alors que l'application utilise {names[current]}. "
                          "Restaurez-la quand l'application utilise le même type de base.")
    safety_path = backups / default_name("avant-restauration-")
    while safety_path.exists() or safety_path.resolve() == Path(src).resolve():  # ne jamais écraser la source ni une sauvegarde
        safety_path = backups / default_name("avant-restauration-")
    safety = create_backup(cfg, safety_path, run=run, storage=storage, sqlite_path=sqlite_path)

    with tempfile.TemporaryDirectory(dir=storage.parent) as tmp_name:
        tmp = Path(tmp_name)
        with zipfile.ZipFile(src) as archive:
            dump = tmp / db_member(engine)
            with archive.open(db_member(engine)) as handle, dump.open("wb") as out:
                shutil.copyfileobj(handle, out)
            staged = tmp / "storage"
            staged.mkdir()
            for name in archive.namelist():
                if not name.startswith(STORAGE_PREFIX) or name.endswith("/"):
                    continue
                target = _safe_target(staged, name[len(STORAGE_PREFIX):])
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(name) as handle, target.open("wb") as out:
                    shutil.copyfileobj(handle, out)

        if cfg.uses_sqlite:
            target = sqlite_path or paths.sqlite_path()
            for suffix in ("-wal", "-shm"):  # journaux de l'ancienne base : ne doivent pas être rejoués sur la nouvelle
                Path(str(target) + suffix).unlink(missing_ok=True)
            os.replace(dump, target)
        else:
            result = run(
                [pg_tool(cfg, "pg_restore"), *_pg_args(cfg), "-d", cfg.postgres.database, "--clean", "--if-exists", "--no-owner",
                 "--no-privileges", "--single-transaction", str(dump)],
                env=_env(cfg), capture_output=True, text=True, creationflags=CREATE_NO_WINDOW,
            )
            if result.returncode != 0:  # --single-transaction : la base est restée intacte
                raise BackupError("La restauration de la base a échoué (état précédent conservé) : " + (result.stderr or "").strip()[-300:])

        # Bascule des captures : l'ancien dossier est conservé à côté, jamais supprimé.
        if storage.exists():
            storage.rename(storage.with_name(f"storage.avant-restauration-{secrets.token_hex(3)}"))
        shutil.move(str(staged), str(storage))
    return safety


def prune(directory: Path, *, prefix: str, keep: int = 5) -> list[Path]:
    """Ne garde que les `keep` sauvegardes les plus récentes portant ce préfixe ; retourne celles supprimées."""
    files = sorted((p for p in directory.glob(f"{prefix}*{EXTENSION}")), key=lambda p: p.stat().st_mtime, reverse=True)
    removed = files[keep:]
    for path in removed:
        path.unlink(missing_ok=True)
    return removed


def database_has_data(cfg: Config, sqlite_path: Path | None = None) -> bool:
    if cfg.uses_sqlite:
        target = sqlite_path or paths.sqlite_path()
        if not target.exists():
            return False
        try:
            conn = sqlite3.connect(f"file:{target.as_posix()}?mode=ro", uri=True, timeout=10)
            try:
                return bool(conn.execute("SELECT count(*) FROM sqlite_master WHERE type = 'table'").fetchone()[0])
            finally:
                conn.close()
        except sqlite3.Error:
            return False
    import psycopg

    pg = cfg.postgres
    try:
        with psycopg.connect(host=pg.host, port=pg.port, dbname=pg.database, user=pg.user, password=pg.password, connect_timeout=6) as conn:
            return bool(conn.execute("SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public'").fetchone()[0])
    except psycopg.Error:
        return False
