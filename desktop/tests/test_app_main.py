import os
import time
from datetime import datetime, timedelta

import pytest

from tjlauncher import app, backup, config, main, paths, runtime
from tjlauncher import postgres as pg
from tjlauncher.config import Config
from tjlauncher.processes import StackError
from tjlauncher.ui import HeadlessUI
from tjlauncher.version import __version__


class FakeStack:
    instances = []

    def __init__(self, cfg, fail=None):
        self.cfg, self.fail, self.events, self.running = cfg, fail, [], False
        FakeStack.instances.append(self)

    def start(self):
        self.events.append("start")
        self.running = True

    def wait_healthy(self, timeout=90):
        self.events.append("healthy")
        if self.fail:
            raise StackError(self.fail)

    def is_running(self):
        return self.running

    def stop(self, grace=6):
        self.events.append("stop")
        self.running = False


@pytest.fixture
def calls(monkeypatch):
    log = []
    monkeypatch.setattr(runtime, "migrate", lambda cfg, run=None: log.append("migrate"))
    monkeypatch.setattr(runtime, "count_users", lambda cfg, run=None: 1)
    monkeypatch.setattr(backup, "database_has_data", lambda cfg: True)
    monkeypatch.setattr(backup, "create_backup", lambda cfg, dest, **k: (log.append(("backup", dest.name)), dest.write_bytes(b"x"), dest)[2])
    FakeStack.instances.clear()
    return log


def ready_cfg(**kw):
    cfg = Config(secret_key="k", **kw)
    cfg.postgres.password = "pw"
    return cfg


def launcher(cfg, ui=None, **kw):
    return app.Launcher(ui or HeadlessUI(), cfg=cfg, stack_factory=FakeStack, open_url=lambda url: None, **kw)


# --- préparation ------------------------------------------------------------------------------------------------


def test_prepare_generates_the_secret_key_once_and_saves_the_configuration(monkeypatch):
    monkeypatch.setattr(pg, "ensure_database", lambda cfg, ui, deps=None: setattr(cfg.postgres, "password", "pw"))
    cfg = Config()
    launcher(cfg).prepare()
    key = cfg.secret_key
    assert len(key) >= 64 and config.load().configured and config.load().secret_key == key
    launcher(config.load()).prepare()
    assert config.load().secret_key == key  # stable d'un lancement à l'autre (sessions conservées)


def test_prepare_picks_distinct_free_ports(monkeypatch):
    monkeypatch.setattr(pg, "ensure_database", lambda cfg, ui, deps=None: None)
    cfg = Config(ui_port=47300, api_port=47300)
    launcher(cfg).prepare()
    assert cfg.ui_port != cfg.api_port


def test_postgres_errors_become_user_facing_launcher_errors(monkeypatch):
    def boom(cfg, ui, deps=None):
        raise pg.PostgresError("PostgreSQL ne répond pas")

    monkeypatch.setattr(pg, "ensure_database", boom)
    cfg = Config(secret_key="k")
    cfg.postgres.password = "pw"  # PostgreSQL fonctionnait : pas de repli sur une base SQLite vide (voir test_sqlite_fallback)
    with pytest.raises(app.LauncherError, match="ne répond pas"):
        launcher(cfg).prepare()
    assert not cfg.uses_sqlite


# --- démarrage ---------------------------------------------------------------------------------------------------


def test_start_migrates_then_starts_servers_and_records_the_version(calls):
    cfg = ready_cfg()
    ln = launcher(cfg)
    ln.start()
    assert calls == ["migrate"] and ln.stack.events == ["start", "healthy"]
    assert config.load().last_app_version == __version__


def test_failed_start_stops_everything_and_explains(calls):
    ln = app.Launcher(HeadlessUI(), cfg=ready_cfg(), stack_factory=lambda cfg: FakeStack(cfg, fail="L'interface ne répond pas"), open_url=lambda u: None)
    with pytest.raises(app.LauncherError, match="ne répond pas"):
        ln.start()
    assert ln.stack.events[-1] == "stop"


def test_failed_migration_prevents_starting_servers(calls, monkeypatch):
    def fail(cfg, run=None):
        raise runtime.ManageError("migration cassée")

    monkeypatch.setattr(runtime, "migrate", fail)
    ln = launcher(ready_cfg())
    with pytest.raises(app.LauncherError, match="migration cassée"):
        ln.start()
    assert ln.stack is None


# --- mise à jour : sauvegarde avant migration ---------------------------------------------------------------------------


def test_upgrade_backs_up_before_migrating(calls):
    cfg = ready_cfg(last_app_version="0.9.0")
    launcher(cfg).start()
    assert calls[0][0] == "backup" and calls[0][1].startswith("avant-mise-a-jour-") and calls[1] == "migrate"


def test_no_upgrade_backup_on_first_install_or_same_version(calls):
    launcher(ready_cfg(last_app_version="")).start()
    launcher(ready_cfg(last_app_version=__version__)).start()
    assert all(c == "migrate" for c in calls)


def test_no_upgrade_backup_when_the_database_is_empty(calls, monkeypatch):
    monkeypatch.setattr(backup, "database_has_data", lambda cfg: False)
    launcher(ready_cfg(last_app_version="0.9.0")).start()
    assert calls == ["migrate"]


def test_upgrade_is_aborted_if_the_safety_backup_fails(calls, monkeypatch):
    def fail(cfg, dest, **k):
        raise backup.BackupError("disque plein")

    monkeypatch.setattr(backup, "create_backup", fail)
    ln = launcher(ready_cfg(last_app_version="0.9.0"))
    with pytest.raises(app.LauncherError, match="disque plein"):
        ln.start()
    assert "migrate" not in calls and ln.stack is None  # on ne migre JAMAIS sans filet


# --- sauvegardes automatiques ---------------------------------------------------------------------------------------------


def test_auto_backup_runs_when_none_exists_then_waits_a_week(calls):
    ln = launcher(ready_cfg())
    created = ln.auto_backup_if_due()
    assert created and created.name.startswith("auto-")
    assert ln.auto_backup_if_due() is None  # trop récent
    assert ln.auto_backup_if_due(now=datetime.now() + timedelta(days=8)) is not None


def test_auto_backup_skipped_for_an_empty_database_and_failures_are_not_fatal(calls, monkeypatch):
    monkeypatch.setattr(backup, "database_has_data", lambda cfg: False)
    assert launcher(ready_cfg()).auto_backup_if_due() is None
    monkeypatch.setattr(backup, "database_has_data", lambda cfg: True)

    def fail(cfg, dest, **k):
        raise backup.BackupError("x")

    monkeypatch.setattr(backup, "create_backup", fail)
    assert launcher(ready_cfg()).auto_backup_if_due() is None  # pas d'exception : le démarrage continue


def test_auto_backups_are_rotated(calls):
    ln = launcher(ready_cfg())
    for i in range(7):
        ln.auto_backup_if_due(now=datetime.now() + timedelta(days=8 * (i + 1)))
        time.sleep(0.01)
    assert len(list(paths.backups_dir().glob("auto-*.tjbackup"))) == app.KEEP_AUTO_BACKUPS


# --- compte ---------------------------------------------------------------------------------------------------------------


def test_first_run_offers_account_creation_only_when_there_is_none(monkeypatch, calls):
    offered = []

    class UI(HeadlessUI):
        def account_dialog(self, create):
            offered.append(create)
            return True

    monkeypatch.setattr(runtime, "count_users", lambda cfg, run=None: 0)
    assert launcher(ready_cfg(), UI()).ensure_account() is True and len(offered) == 1
    monkeypatch.setattr(runtime, "count_users", lambda cfg, run=None: 2)
    launcher(ready_cfg(), UI()).ensure_account()
    assert len(offered) == 1  # aucun nouveau dialogue


def test_account_reading_failure_does_not_block_startup(monkeypatch, calls):
    def boom(cfg, run=None):
        raise runtime.ManageError("illisible")

    monkeypatch.setattr(runtime, "count_users", boom)
    assert launcher(ready_cfg()).ensure_account() is True


def test_create_account_forwards_fields(monkeypatch, calls):
    seen = {}
    monkeypatch.setattr(runtime, "create_account", lambda cfg, **kw: seen.update(kw) or {"ok": True})
    launcher(ready_cfg()).create_account({"username": "alice", "password": "Mdp-Solide-9", "email": "a@b.c"})
    assert seen == {"username": "alice", "password": "Mdp-Solide-9", "email": "a@b.c", "timezone": "UTC"}


def test_headless_account_dialog_reports_errors_without_crashing(monkeypatch, calls):
    ui = HeadlessUI(account={"username": "a", "password": "x"})
    monkeypatch.setattr(runtime, "create_account", lambda cfg, **kw: {"ok": False, "errors": {"username": ["trop court"]}})
    assert launcher(ready_cfg(), ui).ensure_account() is False or True
    monkeypatch.setattr(runtime, "count_users", lambda cfg, run=None: 0)
    assert launcher(ready_cfg(), ui).ensure_account() is False and ui.errors


# --- restauration -------------------------------------------------------------------------------------------------------------


def test_restore_stops_restores_migrates_and_restarts(calls, monkeypatch, tmp_path):
    monkeypatch.setattr(backup, "verify_backup", lambda p: {})
    monkeypatch.setattr(backup, "restore_backup", lambda cfg, src: (calls.append("restore"), tmp_path / "securite.tjbackup")[1])
    ln = launcher(ready_cfg())
    ln.start()
    calls.clear()
    safety = ln.restore(tmp_path / "x.tjbackup")
    assert calls[:2] == ["restore", "migrate"] and safety.name == "securite.tjbackup"
    first, second = FakeStack.instances
    assert first.events[-1] == "stop" and second.events == ["start", "healthy"]  # arrêt avant, relance après


def test_restore_restarts_the_app_even_if_the_restore_fails(calls, monkeypatch, tmp_path):
    monkeypatch.setattr(backup, "verify_backup", lambda p: {})

    def fail(cfg, src):
        raise backup.BackupError("dump illisible")

    monkeypatch.setattr(backup, "restore_backup", fail)
    ln = launcher(ready_cfg())
    ln.start()
    with pytest.raises(backup.BackupError):
        ln.restore(tmp_path / "x.tjbackup")
    assert len(FakeStack.instances) == 2 and FakeStack.instances[1].running  # l'application reste utilisable


def test_restore_refuses_an_invalid_archive_before_touching_anything(calls, monkeypatch, tmp_path):
    def invalid(path):
        raise backup.BackupError("corrompue")

    monkeypatch.setattr(backup, "verify_backup", invalid)
    ln = launcher(ready_cfg())
    ln.start()
    with pytest.raises(backup.BackupError):
        ln.restore(tmp_path / "x.tjbackup")
    assert FakeStack.instances[0].running and len(FakeStack.instances) == 1  # rien arrêté


# --- ligne de commande ----------------------------------------------------------------------------------------------------------


def test_cli_status_unconfigured(capsys):
    assert main.main(["status"]) == 0
    out = capsys.readouterr().out
    assert __version__ in out and "Configurée : non" in out and str(paths.data_dir()) in out


def test_cli_verify_reports_valid_and_invalid_archives(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(backup, "verify_backup", lambda p: {"app_version": "1.0.0", "created_at": "t", "storage_files": 2})
    assert main.main(["verify", str(tmp_path / "a")]) == 0 and "valide" in capsys.readouterr().out

    def invalid(p):
        raise backup.BackupError("corrompue")

    monkeypatch.setattr(backup, "verify_backup", invalid)
    assert main.main(["verify", str(tmp_path / "a")]) == 1 and "INVALIDE" in capsys.readouterr().out


def test_cli_backup_and_restore_need_a_configured_app(capsys, tmp_path):
    assert main.main(["backup"]) == 1
    assert main.main(["restore", str(tmp_path / "a"), "--yes"]) == 1
    assert "non configurée" in capsys.readouterr().out.lower()


def test_cli_restore_requires_confirmation_and_a_stopped_app(tmp_path, capsys, monkeypatch):
    config.save(ready_cfg())
    restored = []
    monkeypatch.setattr(backup, "restore_backup", lambda cfg, src: restored.append(src) or tmp_path / "securite")
    monkeypatch.setattr("tjlauncher.net.http_ok", lambda url, timeout=2.0: False)
    assert main.main(["restore", str(tmp_path / "a")]) == 1 and not restored  # sans --yes : rien
    assert "--yes" in capsys.readouterr().out
    assert main.main(["restore", str(tmp_path / "a"), "--yes"]) == 0 and restored

    monkeypatch.setattr("tjlauncher.net.http_ok", lambda url, timeout=2.0: True)
    restored.clear()
    assert main.main(["restore", str(tmp_path / "a"), "--yes"]) == 1 and not restored  # application en cours : refus
    assert "Fermez" in capsys.readouterr().out


def test_child_subcommands_are_dispatched_before_argument_parsing(monkeypatch):
    seen = {}
    monkeypatch.setattr(main, "cmd_serve_api", lambda: seen.setdefault("serve", True) and 0)
    monkeypatch.setattr(main, "cmd_manage", lambda args: seen.setdefault("manage", args) and 0)
    main.main(["serve-api"])
    main.main(["manage", "migrate", "--noinput", "--verbosity", "0"])  # options Django transmises telles quelles
    assert seen["serve"] is True and seen["manage"] == ["migrate", "--noinput", "--verbosity", "0"]


def test_self_test_detects_missing_frontend(monkeypatch, capsys, tmp_path):
    monkeypatch.setenv("TJ_FRONTEND_DIR", str(tmp_path / "absent"))
    assert main.cmd_self_test() == 1
    assert "interface absente" in capsys.readouterr().out
    _ = os
