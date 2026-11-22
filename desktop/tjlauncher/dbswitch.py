"""Migration des données de SQLite (mode de secours) vers PostgreSQL.

Principes de sécurité des données :
  * la base SQLite n'est JAMAIS modifiée ni supprimée par la migration (elle est renommée seulement après succès) ;
  * une sauvegarde `.tjbackup` est créée avant toute opération ;
  * l'import dans PostgreSQL est atomique (une transaction) et contrôlé ligne par ligne (décompte par table) ;
  * une base PostgreSQL qui contient déjà des données différentes n'est jamais écrasée.
"""
from __future__ import annotations

import dataclasses
import logging
import shutil
import tempfile
from collections.abc import Callable
from pathlib import Path

from . import backup, paths, runtime
from .config import ENGINE_POSTGRES, ENGINE_SQLITE, Config
from .ui import UI

log = logging.getLogger("tjlauncher.dbswitch")


class MigrationError(Exception):
    """Erreur affichable ; les données SQLite sont restées intactes."""


@dataclasses.dataclass
class Ops:
    """Opérations injectables (tests sans processus Django)."""

    migrate: Callable[[Config], None] = runtime.migrate
    row_counts: Callable[[Config], dict[str, int]] = runtime.row_counts
    dump_data: Callable[[Config, Path], None] = runtime.dump_data
    load_data: Callable[[Config, Path], None] = runtime.load_data
    flush: Callable[[Config], None] = runtime.flush
    create_backup: Callable[..., Path] = backup.create_backup


def _view(cfg: Config, engine: str) -> Config:
    """Copie de la configuration vue par le backend avec le moteur donné (l'originale n'est pas modifiée)."""
    return dataclasses.replace(cfg, db_engine=engine)


def _total(counts: dict[str, int]) -> int:
    return sum(counts.values())


def migrate_sqlite_to_postgres(cfg: Config, ui: UI, ops: Ops | None = None) -> dict[str, int]:
    """`cfg` contient déjà les paramètres PostgreSQL utilisables. Retourne le décompte migré par table."""
    ops = ops or Ops()
    source, target = _view(cfg, ENGINE_SQLITE), _view(cfg, ENGINE_POSTGRES)

    try:
        ui.status("Sauvegarde de vos données avant migration…")
        ops.create_backup(source, paths.backups_dir() / backup.default_name("avant-migration-postgresql-"))

        ui.status("Préparation des données SQLite…")
        ops.migrate(source)  # schéma à jour avant l'export
        expected = ops.row_counts(source)

        ui.status("Préparation de la base PostgreSQL…")
        ops.migrate(target)
        existing = ops.row_counts(target)
    except (runtime.ManageError, backup.BackupError) as exc:
        raise MigrationError(str(exc)) from exc

    if _total(existing):
        if existing == expected:  # migration déjà faite (interrompue avant l'enregistrement de la configuration)
            return expected
        raise MigrationError(
            "La base PostgreSQL contient déjà des données différentes de celles de SQLite : rien n'a été copié "
            "pour ne pas écraser vos données. Vos données SQLite sont intactes."
        )

    dump_dir = Path(tempfile.mkdtemp(prefix="migration-", dir=paths.data_dir()))
    try:
        dump = dump_dir / "data.json"
        loaded = False
        try:
            ui.status("Export des données…")
            ops.dump_data(source, dump)
            ui.status("Import dans PostgreSQL…")
            loaded = True  # à partir d'ici un échec peut avoir laissé des lignes : on vide la base cible (elle était vide)
            ops.load_data(target, dump)
            ui.status("Vérification des données copiées…")
            copied = ops.row_counts(target)
            if copied != expected:
                raise MigrationError("Les données copiées ne correspondent pas aux données d'origine (décompte différent).")
        except (runtime.ManageError, MigrationError) as exc:
            if loaded:
                try:
                    ops.flush(target)
                except runtime.ManageError as flush_exc:
                    log.error("Nettoyage de la base cible impossible : %s", flush_exc)
            if isinstance(exc, MigrationError):
                raise
            raise MigrationError(str(exc)) from exc
    finally:
        shutil.rmtree(dump_dir, ignore_errors=True)  # contient des données personnelles en clair
    return expected


def archive_sqlite(sqlite_path: Path | None = None) -> Path | None:
    """Après une migration réussie : met de côté la base SQLite (jamais supprimée) et ses fichiers WAL."""
    path = sqlite_path or paths.sqlite_path()
    if not path.exists():
        return None
    target = path.with_name(f"{path.name}.migre-vers-postgresql")
    n = 1
    while target.exists():
        n += 1
        target = path.with_name(f"{path.name}.migre-vers-postgresql-{n}")
    path.replace(target)
    for suffix in ("-wal", "-shm"):
        Path(str(path) + suffix).unlink(missing_ok=True)
    return target
