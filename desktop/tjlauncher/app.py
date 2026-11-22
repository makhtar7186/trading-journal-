"""Orchestration : premier lancement (PostgreSQL, base, compte) puis démarrage de l'application."""
from __future__ import annotations

import copy
import logging
import webbrowser
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse

from . import backup, config, dbswitch, net, paths, runtime
from . import postgres as pg
from .config import ENGINE_POSTGRES, ENGINE_SQLITE, Config
from .processes import Stack, StackError
from .ui import SetupCancelled, UI
from .version import PG_INSTALLER, __version__

log = logging.getLogger("tjlauncher")
AUTO_BACKUP_EVERY = timedelta(days=7)
AUTO_BACKUP_PREFIX = "auto-"
KEEP_AUTO_BACKUPS = 5
UPGRADE_SNOOZE = timedelta(days=1)  # « Plus tard » ou échec : pas de nouvelle proposition avant ce délai


class LauncherError(Exception):
    """Erreur fatale affichable à l'utilisateur."""


class Launcher:
    def __init__(self, ui: UI, *, cfg: Config | None = None, deps: pg.PgDeps | None = None, stack_factory=Stack,
                 open_url=webbrowser.open, migration_ops: dbswitch.Ops | None = None, online=None, now=datetime.now) -> None:
        self.ui = ui
        self.cfg = cfg or config.load()
        self.deps = deps
        self._stack_factory = stack_factory
        self._open_url = open_url
        self.stack: Stack | None = None
        self._migration_ops = migration_ops
        self._now = now
        self._online = online or (lambda: net.internet_available(urlparse(PG_INSTALLER["url"]).hostname or "www.enterprisedb.com"))

    # -- préparation (chaque lancement ; l'assistant n'intervient que si nécessaire) ------------------------
    def prepare(self) -> None:
        cfg = self.cfg
        if not cfg.secret_key:
            cfg.new_secret_key()
        cfg.ui_port = net.find_free_port(cfg.ui_port)
        cfg.api_port = net.find_free_port(cfg.api_port, avoid={cfg.ui_port})
        if cfg.uses_sqlite:
            self._prepare_sqlite()
        else:
            self._prepare_postgres()
        config.save(cfg)  # dès que la base est prête : un plantage ultérieur ne refait pas l'assistant

    # -- choix du moteur de base de données -------------------------------------------------------------------
    def _prepare_postgres(self) -> None:
        cfg = self.cfg
        first_setup = not cfg.postgres.password  # jamais configuré : PostgreSQL n'a jamais fonctionné ici
        try:
            pg.ensure_database(cfg, self.ui, self.deps)
        except pg.PostgresError as exc:
            if not first_setup:
                # PostgreSQL fonctionnait et ne répond plus : on NE bascule PAS sur une base SQLite vide, qui
                # donnerait l'impression d'avoir perdu les données. L'utilisateur doit réparer son serveur.
                raise LauncherError(str(exc)) from exc
            self._fall_back_to_sqlite(str(exc))

    def _fall_back_to_sqlite(self, reason: str) -> None:
        cfg = self.cfg
        log.warning("PostgreSQL indisponible, repli sur SQLite : %s", reason)
        accepted = self.ui.confirm(
            "PostgreSQL n'a pas pu être configuré",
            f"{reason}\n\nTrading Journal peut fonctionner dès maintenant avec une base SQLite (mode de secours). "
            "Dès que PostgreSQL pourra être installé (connexion Internet rétablie), l'application vous proposera de l'installer "
            "et de migrer vos données automatiquement.\n\nContinuer avec SQLite ?",
        )
        if not accepted:
            raise LauncherError(reason)
        cfg.db_engine, cfg.fallback_reason, cfg.upgrade_snooze_until = ENGINE_SQLITE, reason, ""

    def _snoozed(self) -> bool:
        if not self.cfg.upgrade_snooze_until:
            return False
        try:
            return self._now() < datetime.fromisoformat(self.cfg.upgrade_snooze_until)
        except ValueError:
            return False

    def _snooze(self) -> None:
        self.cfg.upgrade_snooze_until = (self._now() + UPGRADE_SNOOZE).isoformat(timespec="seconds")

    def _prepare_sqlite(self) -> None:
        """Mode de secours : à chaque lancement, si PostgreSQL peut maintenant être installé, on le propose.
        Un échec ici n'empêche JAMAIS le démarrage : l'application continue sur SQLite."""
        if self._snoozed():
            return
        deps = self.deps or pg.PgDeps()
        try:
            if not deps.detect() and not self._online():
                self.ui.status("Mode SQLite (secours) : PostgreSQL sera proposé dès que la connexion Internet sera rétablie.")
                return
            self._offer_upgrade(deps)
        except SetupCancelled:
            self._snooze()
        except Exception as exc:  # noqa: BLE001 (le démarrage prime sur la migration)
            log.exception("Tentative de passage à PostgreSQL interrompue")
            self.cfg.fallback_reason = str(exc)
            self._snooze()

    def _offer_upgrade(self, deps: pg.PgDeps) -> None:
        cfg = self.cfg
        choice = self.ui.choose(
            "Passer à PostgreSQL ?",
            "Trading Journal fonctionne actuellement avec une base SQLite (mode de secours). PostgreSQL peut maintenant être "
            "installé et configuré. Vos données seront copiées vers PostgreSQL (une sauvegarde est créée avant, "
            "et vos données SQLite sont conservées).",
            ["Passer à PostgreSQL maintenant", "Plus tard"],
        )
        if choice != 0:
            self._snooze()
            return
        trial = copy.deepcopy(cfg)
        trial.db_engine = ENGINE_POSTGRES
        try:
            pg.ensure_database(trial, self.ui, deps)
        except pg.PostgresError as exc:
            cfg.postgres = trial.postgres  # conserve ce qui a réussi (ex. serveur installé) pour la prochaine tentative
            cfg.fallback_reason = str(exc)
            self._snooze()
            self.ui.error("PostgreSQL n'a pas pu être configuré", f"{exc}\n\nVous continuez avec SQLite ; nouvelle tentative plus tard.")
            return
        cfg.postgres = trial.postgres  # base prête : un échec de migration ne refait pas l'installation
        config.save(cfg)
        try:
            counts = dbswitch.migrate_sqlite_to_postgres(trial, self.ui, self._migration_ops)
        except dbswitch.MigrationError as exc:
            cfg.fallback_reason = str(exc)
            self._snooze()
            self.ui.error("Migration vers PostgreSQL impossible", f"{exc}\n\nVos données SQLite sont intactes ; vous continuez avec SQLite.")
            return
        cfg.db_engine, cfg.fallback_reason, cfg.upgrade_snooze_until = ENGINE_POSTGRES, "", ""
        config.save(cfg)  # le moteur ne change qu'APRÈS une migration vérifiée
        archived = dbswitch.archive_sqlite()
        log.info("Migration vers PostgreSQL terminée : %s ligne(s) ; ancienne base : %s", sum(counts.values()), archived)
        self.ui.status(f"Migration terminée ({sum(counts.values())} enregistrement(s)). Vous utilisez maintenant PostgreSQL.")

    # -- sauvegardes automatiques -------------------------------------------------------------------------
    def _backup_before_upgrade(self) -> None:
        cfg = self.cfg
        if cfg.last_app_version and cfg.last_app_version != __version__ and backup.database_has_data(cfg):
            self.ui.status("Sauvegarde de vos données avant la mise à jour…")
            try:
                backup.create_backup(cfg, paths.backups_dir() / backup.default_name("avant-mise-a-jour-"))
            except backup.BackupError as exc:
                raise LauncherError(f"Mise à jour interrompue : {exc}") from exc  # on ne migre JAMAIS sans filet

    def auto_backup_if_due(self, now: datetime | None = None) -> Path | None:
        """Sauvegarde hebdomadaire automatique (les 5 dernières sont conservées). Un échec n'empêche pas le démarrage."""
        now = now or datetime.now()
        directory = paths.backups_dir()
        existing = sorted(directory.glob(f"{AUTO_BACKUP_PREFIX}*{backup.EXTENSION}"), key=lambda p: p.stat().st_mtime, reverse=True)
        if existing and now - datetime.fromtimestamp(existing[0].stat().st_mtime) < AUTO_BACKUP_EVERY:
            return None
        if not backup.database_has_data(self.cfg):
            return None
        try:
            path = backup.create_backup(self.cfg, directory / backup.default_name(AUTO_BACKUP_PREFIX))
            backup.prune(directory, prefix=AUTO_BACKUP_PREFIX, keep=KEEP_AUTO_BACKUPS)
            return path
        except backup.BackupError as exc:
            log.warning("Sauvegarde automatique impossible : %s", exc)
            return None

    # -- démarrage ----------------------------------------------------------------------------------------
    def start(self) -> None:
        cfg = self.cfg
        self._backup_before_upgrade()
        self.ui.status("Mise à jour de la base de données…")
        try:
            runtime.migrate(cfg)
        except runtime.ManageError as exc:
            raise LauncherError(str(exc)) from exc
        self.ui.status("Démarrage de l'application…")
        self.stack = self._stack_factory(cfg)
        try:
            self.stack.start()
            self.stack.wait_healthy()
        except StackError as exc:
            self.stack.stop()
            raise LauncherError(str(exc)) from exc
        cfg.last_app_version = __version__
        config.save(cfg)

    def ensure_account(self) -> bool:
        """Au tout premier lancement (aucun compte), propose d'en créer un. Retourne True si un compte existe ensuite."""
        try:
            count = runtime.count_users(self.cfg)
        except runtime.ManageError as exc:
            log.warning("%s", exc)
            return True
        if count > 0:
            return True
        return self.ui.account_dialog(self.create_account)

    def create_account(self, values: dict) -> dict:
        return runtime.create_account(
            self.cfg, username=values.get("username", ""), password=values.get("password", ""),
            email=values.get("email", ""), timezone=values.get("timezone", "UTC"),
        )

    def open_browser(self) -> None:
        self._open_url(self.cfg.ui_url)

    # -- sauvegarde / restauration manuelles -----------------------------------------------------------------
    def backup_now(self, dest: Path | None = None) -> Path:
        dest = dest or paths.backups_dir() / backup.default_name()
        return backup.create_backup(self.cfg, dest)

    def restore(self, src: Path) -> Path:
        """Arrête l'application, restaure, puis la relance. Retourne la sauvegarde de sécurité créée avant."""
        backup.verify_backup(src)
        was_running = self.stack is not None and self.stack.is_running()
        if self.stack:
            self.stack.stop()
        try:
            safety = backup.restore_backup(self.cfg, src)
            runtime.migrate(self.cfg)  # une sauvegarde plus ancienne peut demander des migrations
        finally:
            if was_running:
                self.start()
        return safety

    def stop(self) -> None:
        if self.stack:
            self.stack.stop()
