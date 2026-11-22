import http.server
import json
import subprocess
import sys
import threading
import time

import pytest

from tjlauncher import paths, runtime
from tjlauncher.config import Config, PostgresConfig
from tjlauncher.processes import KillOnCloseJob, Stack, StackError


def cfg():
    c = Config(ui_port=48100, api_port=48101, secret_key="SECRET-DJANGO")
    c.postgres = PostgresConfig(host="127.0.0.1", port=5433, database="tjdb", user="tjuser", password="PG-APP-PASSWORD")
    return c


# --- environnement du backend -----------------------------------------------------------------------------------


def test_backend_env_contains_the_configuration_and_binds_locally():
    env = runtime.backend_env(cfg(), base={"PATH": "x", "SystemRoot": "C:\\Windows"})
    assert env["DJANGO_SETTINGS_MODULE"] == "config.settings.desktop"
    assert (env["POSTGRES_DB"], env["POSTGRES_USER"], env["POSTGRES_PASSWORD"], env["POSTGRES_PORT"]) == ("tjdb", "tjuser", "PG-APP-PASSWORD", "5433")
    assert env["API_HOST"] == "127.0.0.1" and env["API_PORT"] == "48101"
    assert env["CSRF_TRUSTED_ORIGINS"] == "http://127.0.0.1:48100,http://localhost:48100"
    assert env["ALLOW_REGISTRATION"] == "true" and env["STORAGE_BACKEND"] == "local"
    assert env["PATH"] == "x" and env["SystemRoot"] == "C:\\Windows"  # le nécessaire pour lancer un processus Windows est conservé


def test_backend_env_drops_inherited_development_settings():
    dirty = {"DJANGO_SETTINGS_MODULE": "config.settings.dev", "POSTGRES_HOST": "db", "DJANGO_ALLOWED_HOSTS": "*", "S3_BUCKET": "b",
             "STORAGE_BACKEND": "s3", "ALLOW_REGISTRATION": "false", "PATH": "p"}
    env = runtime.backend_env(cfg(), base=dirty)
    assert env["DJANGO_SETTINGS_MODULE"] == "config.settings.desktop" and env["POSTGRES_HOST"] == "127.0.0.1"
    assert "DJANGO_ALLOWED_HOSTS" not in env and "S3_BUCKET" not in env
    assert env["STORAGE_BACKEND"] == "local" and env["ALLOW_REGISTRATION"] == "true"


def test_frontend_env_never_receives_backend_secrets_and_listens_locally_only():
    stack = Stack(cfg(), popen=None, job=KillOnCloseJob())
    env = stack.ui_env(base={"DJANGO_SECRET_KEY": "x", "POSTGRES_PASSWORD": "y", "PATH": "p"})
    assert env["HOSTNAME"] == "127.0.0.1" and env["PORT"] == "48100" and env["BACKEND_INTERNAL_URL"] == "http://127.0.0.1:48101"
    assert env["NODE_ENV"] == "production"
    assert not [k for k in env if k.startswith(("DJANGO_", "POSTGRES_"))]
    assert "SECRET-DJANGO" not in json.dumps(env) and "PG-APP-PASSWORD" not in json.dumps(env)


# --- commandes de gestion --------------------------------------------------------------------------------------------


class Result:
    def __init__(self, stdout="", stderr="", code=0):
        self.stdout, self.stderr, self.returncode = stdout, stderr, code


def test_account_password_goes_through_stdin_not_arguments():
    captured = {}

    def run(cmd, **kwargs):
        captured.update(cmd=cmd, **kwargs)
        return Result('{"ok": true, "username": "alice"}')

    out = runtime.create_account(cfg(), username="alice", password="Tres-Secret-9", email="a@b.c", run=run)
    assert out == {"ok": True, "username": "alice"}
    assert "Tres-Secret-9" not in " ".join(captured["cmd"])
    assert json.loads(captured["input"])["password"] == "Tres-Secret-9" and captured["cmd"][-1] == "register_user"
    assert captured["cmd"][-2] == "manage"


def test_account_errors_are_returned_structured():
    out = runtime.create_account(cfg(), username="a", password="x", run=lambda *a, **k: Result('{"ok": false, "errors": {"username": ["trop court"]}}', code=2))
    assert out == {"ok": False, "errors": {"username": ["trop court"]}}


def test_unreadable_manage_output_is_reported_without_crashing():
    out = runtime.create_account(cfg(), username="alice", password="x", run=lambda *a, **k: Result("", "Traceback...", 1))
    assert out["ok"] is False and "detail" in out["errors"]


def test_count_users_and_migrate_errors():
    assert runtime.count_users(cfg(), run=lambda *a, **k: Result("avertissement\n3\n")) == 3
    with pytest.raises(runtime.ManageError, match="lire les comptes"):
        runtime.count_users(cfg(), run=lambda *a, **k: Result("", "boom", 1))
    with pytest.raises(runtime.ManageError, match="migrations"):
        runtime.migrate(cfg(), run=lambda *a, **k: Result("", "relation manquante", 1))
    runtime.migrate(cfg(), run=lambda *a, **k: Result("ok"))


# --- processus -------------------------------------------------------------------------------------------------------------


class FakeProc:
    def __init__(self, exit_code=None):
        self.exit_code, self.terminated, self.killed, self._handle = exit_code, False, False, 0

    def poll(self):
        return self.exit_code

    def terminate(self):
        self.terminated = True
        self.exit_code = 0

    def kill(self):
        self.killed = True

    def wait(self, timeout=None):
        return self.exit_code


class NoJob:
    def add(self, process):
        return True


@pytest.fixture
def frontend(tmp_path, monkeypatch):
    (tmp_path / "server.js").write_text("// serveur")
    monkeypatch.setenv("TJ_FRONTEND_DIR", str(tmp_path))
    monkeypatch.setenv("TJ_NODE", str(tmp_path / "node.exe"))
    return tmp_path


def test_start_launches_api_and_ui_with_the_right_environment(frontend):
    launched = []

    def popen(cmd, **kwargs):
        launched.append((cmd, kwargs))
        return FakeProc()

    stack = Stack(cfg(), popen=popen, job=NoJob())
    stack.start()
    (api_cmd, api_kw), (ui_cmd, ui_kw) = launched
    assert api_cmd[-1] == "serve-api" and api_kw["env"]["API_PORT"] == "48101" and api_kw["env"]["POSTGRES_PASSWORD"] == "PG-APP-PASSWORD"
    assert ui_cmd[-1].endswith("server.js") and ui_kw["env"]["HOSTNAME"] == "127.0.0.1" and ui_kw["cwd"] == str(frontend)
    assert "POSTGRES_PASSWORD" not in ui_kw["env"]
    assert api_kw["creationflags"] & 0x08000000  # aucune fenêtre console


def test_missing_frontend_is_reported(tmp_path, monkeypatch):
    monkeypatch.setenv("TJ_FRONTEND_DIR", str(tmp_path / "absent"))
    with pytest.raises(StackError, match="Interface introuvable"):
        Stack(cfg(), popen=lambda *a, **k: FakeProc(), job=NoJob()).start()


def test_stop_terminates_children_then_kills_stragglers(frontend):
    class Stubborn(FakeProc):
        def terminate(self):
            self.terminated = True

        def wait(self, timeout=None):
            raise subprocess.TimeoutExpired("x", timeout)

    procs = [Stubborn(), FakeProc()]
    stack = Stack(cfg(), popen=lambda *a, **k: procs.pop(0), job=NoJob())
    stack.start()
    api, ui = stack.api, stack.ui
    stack.stop(grace=0.01)
    assert api.terminated and ui.terminated and api.killed and not ui.killed
    assert stack.api is None and stack.ui is None


def test_health_waiting_reports_a_dead_process_with_its_log(frontend):
    stack = Stack(cfg(), popen=lambda *a, **k: FakeProc(exit_code=3), job=NoJob())
    stack.start()
    with pytest.raises(StackError, match="code 3"):
        stack.wait_healthy(timeout=0.5)


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, *args):
        pass


def serve(port):
    server = http.server.ThreadingHTTPServer(("127.0.0.1", port), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def test_wait_healthy_succeeds_when_both_servers_answer(frontend):
    from tjlauncher import net

    api_port, ui_port = net.find_free_port(49200), net.find_free_port(49300)
    config = cfg()
    config.api_port, config.ui_port = api_port, ui_port
    servers = [serve(api_port), serve(ui_port)]
    try:
        stack = Stack(config, popen=lambda *a, **k: FakeProc(), job=NoJob())
        stack.start()
        stack.wait_healthy(timeout=5)
        assert stack.is_running()
    finally:
        for s in servers:
            s.shutdown()


def test_job_object_kills_children_when_the_launcher_goes_away():
    """Vrai test Windows : un processus placé dans le job meurt à la fermeture du job (plantage du lanceur)."""
    job = KillOnCloseJob()
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"], creationflags=0x08000000)
    try:
        assert job.add(child)
        assert child.poll() is None
        import ctypes

        ctypes.windll.kernel32.CloseHandle(job.handle)
        job.handle = None
        for _ in range(50):
            if child.poll() is not None:
                break
            time.sleep(0.1)
        assert child.poll() is not None
    finally:
        if child.poll() is None:
            child.kill()


def test_data_dir_is_under_localappdata_by_default_and_overridable(monkeypatch, tmp_path):
    monkeypatch.delenv("TJ_DATA_DIR")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    assert paths.data_dir() == tmp_path / "local" / "TradingJournal"
    monkeypatch.setenv("TJ_DATA_DIR", str(tmp_path / "ailleurs"))
    assert paths.data_dir() == tmp_path / "ailleurs" and (tmp_path / "ailleurs").is_dir()
