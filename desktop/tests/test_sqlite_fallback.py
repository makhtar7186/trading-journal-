"""Mode de secours SQLite : repli, proposition de migration, migration vérifiée, sauvegardes."""
import sqlite3
from datetime import datetime, timedelta

import pytest

from tjlauncher import app, backup, config, dbswitch, paths, runtime
from tjlauncher import postgres as pg
from tjlauncher.config import ENGINE_POSTGRES, ENGINE_SQLITE, Config
from tjlauncher.ui import HeadlessUI, SetupCancelled


class RecordingUI(HeadlessUI):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.confirms, self.choices = [], []

    def confirm(self, title, message):
        self.confirms.append((title, message))
        return super().confirm(title, message)

    def choose(self, title, message, options):
        self.choices.append((title, options))
        return super().choose(title, message, options)


def launcher(cfg, ui=None, **kw):
    return app.Launcher(ui or RecordingUI(), cfg=cfg, open_url=lambda url: None, deps=kw.pop("deps", None), **kw)


def failing_ensure(message="Téléchargement impossible : pas d'Internet"):
    def ensure(cfg, ui, deps=None):
        raise pg.PostgresError(message)

    return ensure


# --- repli au premier lancement ----------------------------------------------------------------------------------------


def test_first_setup_failure_falls_back_to_sqlite_after_confirmation(monkeypatch):
    monkeypatch.setattr(pg, "ensure_database", failing_ensure())
    ui = RecordingUI(confirm=True)
    cfg = Config()
    launcher(cfg, ui).prepare()
    assert cfg.uses_sqlite and "pas d'Internet" in cfg.fallback_reason and cfg.configured
    assert "Continuer avec SQLite" in ui.confirms[0][1] and "pas d'Internet" in ui.confirms[0][1]
    saved = config.load()
    assert saved.uses_sqlite and saved.configured  # un 2e lancement ne refait pas l'assistant PostgreSQL


def test_refusing_the_fallback_stops_with_the_original_error(monkeypatch):
    monkeypatch.setattr(pg, "ensure_database", failing_ensure("UAC refusée"))
    cfg = Config()
    with pytest.raises(app.LauncherError, match="UAC refusée"):
        launcher(cfg, RecordingUI(confirm=False)).prepare()
    assert not cfg.uses_sqlite and not config.load().configured


def test_a_previously_working_postgres_that_stops_never_switches_to_an_empty_sqlite(monkeypatch):
    """Sinon l'utilisateur croirait avoir perdu ses données : on lui demande de réparer son serveur."""
    monkeypatch.setattr(pg, "ensure_database", failing_ensure("PostgreSQL ne répond pas"))
    cfg = Config(secret_key="k")
    cfg.postgres.password = "pw"
    ui = RecordingUI(confirm=True)
    with pytest.raises(app.LauncherError, match="ne répond pas"):
        launcher(cfg, ui).prepare()
    assert not cfg.uses_sqlite and ui.confirms == []


def test_cancelling_the_wizard_is_not_a_fallback(monkeypatch):
    def cancel(cfg, ui, deps=None):
        raise SetupCancelled()

    monkeypatch.setattr(pg, "ensure_database", cancel)
    with pytest.raises(SetupCancelled):
        launcher(Config()).prepare()


def test_partial_postgres_progress_is_kept_for_the_next_attempt(monkeypatch):
    """Serveur installé par nous mais base non créée : le mot de passe superutilisateur doit survivre au repli."""
    def partial(cfg, ui, deps=None):
        cfg.postgres.managed, cfg.postgres.superuser_password = True, "super-secret"
        raise pg.PostgresError("création de la base impossible")

    monkeypatch.setattr(pg, "ensure_database", partial)
    cfg = Config()
    launcher(cfg).prepare()
    reloaded = config.load()
    assert reloaded.uses_sqlite and reloaded.postgres.managed and reloaded.postgres.superuser_password == "super-secret"
    assert not reloaded.postgres.password


def test_config_roundtrip_and_unknown_engine_defaults_to_postgres(tmp_path):
    cfg = Config(secret_key="k", db_engine=ENGINE_SQLITE, fallback_reason="r", upgrade_snooze_until="2030-01-01T00:00:00")
    config.save(cfg)
    assert config.load().db_engine == ENGINE_SQLITE and config.load().fallback_reason == "r"
    path = paths.config_path()
    path.write_text(path.read_text(encoding="utf-8").replace('"sqlite"', '"mysql"'), encoding="utf-8")
    assert config.load().db_engine == ENGINE_POSTGRES


def test_backend_environment_selects_the_engine():
    env = runtime.backend_env(Config(secret_key="k", db_engine=ENGINE_SQLITE), base={"DB_ENGINE": "evil"})
    assert env["DB_ENGINE"] == "sqlite" and env["SQLITE_PATH"] == str(paths.sqlite_path())
    assert runtime.backend_env(Config(secret_key="k"), base={})["DB_ENGINE"] == "postgres"


# --- proposition de migration au lancement suivant --------------------------------------------------------------------------


def sqlite_cfg(**kw):
    return Config(secret_key="k", db_engine=ENGINE_SQLITE, fallback_reason="pas d'Internet", **kw)


class FakeDeps:
    def __init__(self, installs=()):
        self._installs = list(installs)

    def detect(self):
        return self._installs


class RecordingOps(dbswitch.Ops):
    def __init__(self, **kw):
        self.events = []
        super().__init__(
            migrate=lambda cfg: self.events.append(("migrate", cfg.db_engine)),
            row_counts=lambda cfg: kw.get("counts", {}).get(cfg.db_engine, {"trades.Trade": 3, "accounts.User": 1}),
            dump_data=lambda cfg, dest: (self.events.append(("dump", cfg.db_engine)), dest.write_text("[]", encoding="utf-8")),
            load_data=lambda cfg, src: self.events.append(("load", cfg.db_engine)),
            flush=lambda cfg: self.events.append(("flush", cfg.db_engine)),
            create_backup=lambda cfg, dest, **k: (self.events.append(("backup", cfg.db_engine)), dest)[1],
        )


def make_target_counts(sqlite=None, postgres=None):
    """Décomptes avant/après : la base cible est vide puis contient les données copiées."""
    return {ENGINE_SQLITE: sqlite or {"trades.Trade": 3, "accounts.User": 1}, ENGINE_POSTGRES: postgres}


class StatefulOps(RecordingOps):
    """La base PostgreSQL est vide jusqu'au `load_data`, comme en réalité."""

    def __init__(self, loaded_counts=None, fail_load=False, preexisting=None):
        super().__init__()
        self.loaded = False
        source = {"trades.Trade": 3, "accounts.User": 1}
        state = {"pg": preexisting or {"trades.Trade": 0, "accounts.User": 0}}

        def counts(cfg):
            return dict(source) if cfg.db_engine == ENGINE_SQLITE else dict(state["pg"])

        def load(cfg, src):
            self.events.append(("load", cfg.db_engine))
            if fail_load:
                raise runtime.ManageError("violation de contrainte")
            state["pg"] = loaded_counts or dict(source)

        self.row_counts, self.load_data = counts, load
        self.flush = lambda cfg: (self.events.append(("flush", cfg.db_engine)), state.update(pg={"trades.Trade": 0, "accounts.User": 0}))


def ensure_ok(monkeypatch):
    def ensure(cfg, ui, deps=None):
        cfg.postgres.password, cfg.postgres.port = "pg-secret", 5432

    monkeypatch.setattr(pg, "ensure_database", ensure)


def touch_sqlite():
    paths.sqlite_path().write_bytes(b"SQLite format 3\0")


def test_offline_without_postgres_stays_on_sqlite_silently(monkeypatch):
    called = []
    monkeypatch.setattr(pg, "ensure_database", lambda *a, **k: called.append(1))
    ui = RecordingUI()
    cfg = sqlite_cfg()
    launcher(cfg, ui, deps=FakeDeps(), online=lambda: False).prepare()
    assert cfg.uses_sqlite and called == [] and ui.choices == []
    assert any("connexion Internet" in m for m in ui.messages)


def test_online_proposes_the_switch_and_migrates_with_verification(monkeypatch):
    ensure_ok(monkeypatch)
    touch_sqlite()
    ops, ui = StatefulOps(), RecordingUI(choice=0)
    cfg = sqlite_cfg()
    launcher(cfg, ui, deps=FakeDeps(), online=lambda: True, migration_ops=ops).prepare()
    assert ui.choices[0][0] == "Passer à PostgreSQL ?"
    assert cfg.db_engine == ENGINE_POSTGRES and cfg.postgres.password == "pg-secret" and cfg.fallback_reason == ""
    assert config.load().db_engine == ENGINE_POSTGRES
    kinds = [e[0] for e in ops.events]
    assert kinds == ["backup", "migrate", "migrate", "dump", "load"]  # sauvegarde AVANT tout, import en dernier
    assert ops.events[3][1] == ENGINE_SQLITE and ops.events[4][1] == ENGINE_POSTGRES
    assert not paths.sqlite_path().exists()
    kept = list(paths.data_dir().glob("trading_journal.sqlite3.migre-vers-postgresql*"))
    assert len(kept) == 1  # l'ancienne base est conservée, jamais supprimée
    assert not list(paths.data_dir().glob("migration-*"))  # l'export en clair est supprimé


def test_later_snoozes_for_a_day_and_keeps_sqlite(monkeypatch):
    ensure_ok(monkeypatch)
    now = datetime(2026, 11, 16, 10, 0, 0)
    cfg = sqlite_cfg()
    ui = RecordingUI(choice=1)
    launcher(cfg, ui, deps=FakeDeps(), online=lambda: True, now=lambda: now).prepare()
    assert cfg.uses_sqlite and cfg.upgrade_snooze_until == (now + timedelta(days=1)).isoformat(timespec="seconds")
    ui2 = RecordingUI(choice=0)
    launcher(cfg, ui2, deps=FakeDeps(), online=lambda: True, now=lambda: now + timedelta(hours=2)).prepare()
    assert ui2.choices == []  # pas de harcèlement
    ui3 = RecordingUI(choice=1)
    launcher(cfg, ui3, deps=FakeDeps(), online=lambda: True, now=lambda: now + timedelta(days=1, minutes=1)).prepare()
    assert len(ui3.choices) == 1  # le lendemain, on repropose


def test_installed_postgres_is_offered_even_without_internet(monkeypatch):
    ensure_ok(monkeypatch)
    touch_sqlite()
    ui = RecordingUI(choice=0)
    cfg = sqlite_cfg()
    launcher(cfg, ui, deps=FakeDeps(installs=[object()]), online=lambda: False, migration_ops=StatefulOps()).prepare()
    assert cfg.db_engine == ENGINE_POSTGRES


def test_postgres_setup_failure_keeps_sqlite_and_never_blocks_startup(monkeypatch):
    monkeypatch.setattr(pg, "ensure_database", failing_ensure("signature invalide"))
    ui = RecordingUI(choice=0)
    cfg = sqlite_cfg()
    launcher(cfg, ui, deps=FakeDeps(), online=lambda: True).prepare()
    assert cfg.uses_sqlite and "signature invalide" in cfg.fallback_reason and cfg.upgrade_snooze_until
    assert any("signature invalide" in e for e in ui.errors)


def test_unexpected_crash_during_the_offer_never_blocks_startup(monkeypatch):
    def crash(*a, **k):
        raise RuntimeError("bug inattendu")

    monkeypatch.setattr(pg, "ensure_database", crash)
    cfg = sqlite_cfg()
    launcher(cfg, RecordingUI(choice=0), deps=FakeDeps(), online=lambda: True).prepare()
    assert cfg.uses_sqlite and cfg.upgrade_snooze_until


def test_cancelling_during_the_switch_keeps_sqlite(monkeypatch):
    def cancel(cfg, ui, deps=None):
        raise SetupCancelled()

    monkeypatch.setattr(pg, "ensure_database", cancel)
    cfg = sqlite_cfg()
    launcher(cfg, RecordingUI(choice=0), deps=FakeDeps(), online=lambda: True).prepare()
    assert cfg.uses_sqlite and cfg.upgrade_snooze_until


# --- sûreté de la migration -------------------------------------------------------------------------------------------------


def run_migration(monkeypatch, ops):
    ensure_ok(monkeypatch)
    touch_sqlite()
    ui = RecordingUI(choice=0)
    cfg = sqlite_cfg()
    launcher(cfg, ui, deps=FakeDeps(), online=lambda: True, migration_ops=ops).prepare()
    return cfg, ui


def test_failed_import_flushes_the_target_and_keeps_sqlite_intact(monkeypatch):
    ops = StatefulOps(fail_load=True)
    cfg, ui = run_migration(monkeypatch, ops)
    assert cfg.uses_sqlite and ("flush", ENGINE_POSTGRES) in ops.events
    assert paths.sqlite_path().exists()  # données d'origine intactes
    assert cfg.postgres.password == "pg-secret"  # la base prête est retenue : pas de réinstallation à la prochaine tentative
    assert any("violation de contrainte" in e for e in ui.errors) and "intactes" in ui.errors[0]
    assert not list(paths.data_dir().glob("migration-*"))


def test_count_mismatch_after_import_is_a_failure(monkeypatch):
    ops = StatefulOps(loaded_counts={"trades.Trade": 2, "accounts.User": 1})  # un trade manquant
    cfg, ui = run_migration(monkeypatch, ops)
    assert cfg.uses_sqlite and ("flush", ENGINE_POSTGRES) in ops.events and paths.sqlite_path().exists()
    assert any("décompte" in e for e in ui.errors)


def test_a_postgres_database_with_different_data_is_never_overwritten(monkeypatch):
    ops = StatefulOps(preexisting={"trades.Trade": 9, "accounts.User": 1})
    cfg, ui = run_migration(monkeypatch, ops)
    kinds = [e[0] for e in ops.events]
    assert cfg.uses_sqlite and "load" not in kinds and "flush" not in kinds and "dump" not in kinds
    assert any("déjà des données" in e for e in ui.errors)


def test_already_migrated_postgres_is_recognised_after_an_interrupted_run(monkeypatch):
    """Plantage entre l'import et l'enregistrement de la configuration : la relance termine sans rien dupliquer."""
    ops = StatefulOps(preexisting={"trades.Trade": 3, "accounts.User": 1})
    cfg, _ = run_migration(monkeypatch, ops)
    kinds = [e[0] for e in ops.events]
    assert cfg.db_engine == ENGINE_POSTGRES and "load" not in kinds and "dump" not in kinds


def test_schema_migration_failure_on_the_source_is_reported(monkeypatch):
    ops = StatefulOps()

    def broken(cfg):
        raise runtime.ManageError("migration cassée")

    ops.migrate = broken
    cfg, ui = run_migration(monkeypatch, ops)
    assert cfg.uses_sqlite and any("migration cassée" in e for e in ui.errors)


# --- sauvegarde / restauration avec SQLite --------------------------------------------------------------------------------


def make_sqlite(path, rows):
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE trade (id INTEGER PRIMARY KEY, name TEXT)")
    conn.executemany("INSERT INTO trade (name) VALUES (?)", [(r,) for r in rows])
    conn.commit()
    conn.close()


def read_names(path):
    conn = sqlite3.connect(path)
    try:
        return [r[0] for r in conn.execute("SELECT name FROM trade ORDER BY id")]
    finally:
        conn.close()


def test_sqlite_backup_roundtrip_including_a_database_open_in_wal_mode(tmp_path):
    db = tmp_path / "db.sqlite3"
    make_sqlite(db, ["EURUSD", "BTC"])
    holder = sqlite3.connect(db)  # base ouverte par « l'application »
    holder.execute("PRAGMA journal_mode=WAL")
    holder.execute("INSERT INTO trade (name) VALUES ('GOLD')")
    holder.commit()
    cfg = sqlite_cfg()
    out = backup.create_backup(cfg, tmp_path / "b.tjbackup", sqlite_path=db, storage=tmp_path / "none")
    manifest = backup.verify_backup(out)
    assert manifest["engine"] == "sqlite" and backup.database_has_data(cfg, sqlite_path=db)
    holder.execute("DELETE FROM trade")
    holder.commit()
    holder.close()
    backup.restore_backup(cfg, out, sqlite_path=db, storage=tmp_path / "storage", backups=tmp_path / "safe")
    assert read_names(db) == ["EURUSD", "BTC", "GOLD"]
    safeties = list((tmp_path / "safe").glob("avant-restauration-*"))
    assert len(safeties) == 1 and backup.verify_backup(safeties[0])["engine"] == "sqlite"


def test_cross_engine_restore_is_refused_before_touching_anything(tmp_path):
    db = tmp_path / "db.sqlite3"
    make_sqlite(db, ["A"])
    sqlite_backup = backup.create_backup(sqlite_cfg(), tmp_path / "s.tjbackup", sqlite_path=db, storage=tmp_path / "none")
    pg_cfg = Config(secret_key="k")
    with pytest.raises(backup.BackupError, match="même type de base"):
        backup.restore_backup(pg_cfg, sqlite_backup, sqlite_path=db, storage=tmp_path / "storage", backups=tmp_path / "safe")
    assert read_names(db) == ["A"] and not (tmp_path / "safe").exists()


def test_database_has_data_for_missing_or_empty_sqlite(tmp_path):
    cfg = sqlite_cfg()
    assert not backup.database_has_data(cfg, sqlite_path=tmp_path / "nope.sqlite3")
    sqlite3.connect(tmp_path / "vide.sqlite3").close()
    assert not backup.database_has_data(cfg, sqlite_path=tmp_path / "vide.sqlite3")


def test_old_postgres_backups_without_an_engine_field_still_verify(tmp_path):
    import json
    import zipfile
    import hashlib

    data = b"DUMP"
    path = tmp_path / "old.tjbackup"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("manifest.json", json.dumps({"format": 1, "app_version": "1.0.0", "created_at": "x", "database": "d",
                                                "db_sha256": hashlib.sha256(data).hexdigest(), "db_bytes": 4, "storage_files": 0}))
        z.writestr("db.dump", data)
    assert backup.verify_backup(path)["format"] == 1
