from pathlib import Path

import pytest

from tjlauncher import elevation, paths
from tjlauncher import postgres as pg
from tjlauncher.config import Config
from tjlauncher.ui import HeadlessUI, SetupCancelled


def fake_install(tmp_path, version="17.10", service="postgresql-x64-17"):
    bin_dir = tmp_path / "PostgreSQL" / version.split(".")[0] / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    (bin_dir / "pg_dump.exe").write_bytes(b"")
    return pg.PgInstall(version, bin_dir, service, None)


class Recorder:
    """Dépendances factices : enregistre les appels, comportements configurables."""

    def __init__(self, *, installs=(), port=5432, valid_logins=(), state="RUNNING", installed=None):
        self.installs = list(installs)
        self.port = port
        self.valid = set(valid_logins)  # {(user, password)}
        self.state = state
        self.calls = []
        self.installed = installed

    def deps(self):
        def can_login(host, port, user, password, database="postgres"):
            return (user, password) in self.valid

        def provision(host, port, su, sp, db, role, rp):
            self.calls.append(("provision", host, port, su, sp, db, role, rp))
            self.valid.add((role, rp))

        def start(name):
            self.calls.append(("start", name))
            self.state = "RUNNING"

        def install(ui):
            self.calls.append(("install",))
            self.valid.add(("postgres", self.installed.super_password))
            return self.installed

        return pg.PgDeps(detect=lambda: list(self.installs), service_state=lambda name: self.state, start_service=start,
                         find_port=lambda: self.port, can_login=can_login, provision=provision, install=install, sleep=lambda s: None)

    def provisioned(self):
        return [c for c in self.calls if c[0] == "provision"]


def new_cfg():
    return Config()


# --- chemin rapide ---------------------------------------------------------------------------------------


def test_already_configured_and_reachable_does_nothing():
    cfg = new_cfg()
    cfg.postgres.password = "app-pass"
    rec = Recorder(valid_logins={(cfg.postgres.user, "app-pass")})
    ui = HeadlessUI()
    pg.ensure_database(cfg, ui, rec.deps())
    assert rec.calls == [] and cfg.postgres.password == "app-pass"


# --- PostgreSQL déjà présent -------------------------------------------------------------------------------


def test_existing_server_asks_for_the_postgres_password_then_provisions(tmp_path):
    install = fake_install(tmp_path)
    rec = Recorder(installs=[install], port=5432, valid_logins={("postgres", "mdp-du-user")})
    cfg = new_cfg()
    pg.ensure_database(cfg, HeadlessUI(secret="mdp-du-user"), rec.deps())

    [(_, host, port, su, sp, db, role, rp)] = rec.provisioned()
    assert (host, port, su, sp, db, role) == ("127.0.0.1", 5432, "postgres", "mdp-du-user", "trading_journal", "trading_journal")
    assert rp != "mdp-du-user" and len(rp) >= 24
    assert cfg.postgres.password == rp and cfg.postgres.port == 5432 and cfg.postgres.bin_dir == str(install.bin_dir)
    assert cfg.postgres.service == "postgresql-x64-17"
    assert cfg.postgres.superuser_password == "" and not cfg.postgres.managed  # jamais conservé : ce serveur n'est pas le nôtre
    assert ("install",) not in rec.calls  # on ne réinstalle JAMAIS un serveur existant


def test_wrong_superuser_password_is_asked_again_up_to_three_times(tmp_path):
    rec = Recorder(installs=[fake_install(tmp_path)], valid_logins={("postgres", "bon")})
    answers = iter(["faux1", "faux2", "bon"])
    asked = []

    class AskingUI(HeadlessUI):
        def ask_secret(self, title, message, error=None):
            asked.append(error)
            return next(answers)

    cfg = new_cfg()
    pg.ensure_database(cfg, AskingUI(), rec.deps())
    assert asked == [None, "Mot de passe incorrect.", "Mot de passe incorrect."]
    assert rec.provisioned()


def test_three_wrong_passwords_fail_without_provisioning(tmp_path):
    rec = Recorder(installs=[fake_install(tmp_path)], valid_logins={("postgres", "bon")})

    class WrongUI(HeadlessUI):
        def ask_secret(self, title, message, error=None):
            return "faux"

    with pytest.raises(pg.PostgresError, match="incorrect"):
        pg.ensure_database(new_cfg(), WrongUI(), rec.deps())
    assert not rec.provisioned()


def test_cancelling_the_password_prompt_cancels_setup(tmp_path):
    rec = Recorder(installs=[fake_install(tmp_path)])
    with pytest.raises(SetupCancelled):
        pg.ensure_database(new_cfg(), HeadlessUI(secret=None), rec.deps())
    assert not rec.provisioned()


def test_stopped_service_is_started_before_asking_anything(tmp_path):
    rec = Recorder(installs=[fake_install(tmp_path)], port=None, state="STOPPED", valid_logins={("postgres", "mdp")})
    ports = iter([None, 5432, 5432, 5432])
    deps = rec.deps()
    deps.find_port = lambda: next(ports, 5432)
    pg.ensure_database(new_cfg(), HeadlessUI(secret="mdp"), deps)
    assert ("start", "postgresql-x64-17") in rec.calls and rec.provisioned()


def test_installed_but_not_answering_and_no_service_gives_actionable_error(tmp_path):
    rec = Recorder(installs=[fake_install(tmp_path, service=None)], port=None, state=None)
    with pytest.raises(pg.PostgresError, match="ne répond pas"):
        pg.ensure_database(new_cfg(), HeadlessUI(secret="x"), rec.deps())


def test_previously_installed_by_us_reuses_stored_superuser_without_prompt(tmp_path):
    cfg = new_cfg()
    cfg.postgres.managed = True
    cfg.postgres.superuser_password = "memorise"
    rec = Recorder(installs=[fake_install(tmp_path)], valid_logins={("postgres", "memorise")})

    class NoPrompt(HeadlessUI):
        def ask_secret(self, *a, **k):
            raise AssertionError("aucune question attendue")

    pg.ensure_database(cfg, NoPrompt(), rec.deps())
    assert rec.provisioned()[0][4] == "memorise" and cfg.postgres.managed and cfg.postgres.superuser_password == "memorise"


def test_reconfiguring_after_losing_config_keeps_the_existing_database_name(tmp_path):
    cfg = new_cfg()  # config perdue : on re-provisionne ; provision_database réutilise la base si elle existe
    rec = Recorder(installs=[fake_install(tmp_path)], valid_logins={("postgres", "p")})
    pg.ensure_database(cfg, HeadlessUI(secret="p"), rec.deps())
    assert rec.provisioned()[0][5] == "trading_journal"


def test_app_login_failure_after_provisioning_is_reported(tmp_path):
    rec = Recorder(installs=[fake_install(tmp_path)], valid_logins={("postgres", "p")})
    deps = rec.deps()
    deps.provision = lambda *a: None  # « réussit » mais la connexion applicative reste impossible
    with pytest.raises(pg.PostgresError, match="connexion avec le compte de l'application échoue"):
        pg.ensure_database(new_cfg(), HeadlessUI(secret="p"), deps)


# --- PostgreSQL absent --------------------------------------------------------------------------------------


def installed_result(tmp_path, port=5433):
    return pg.InstallResult(fake_install(tmp_path, "17.12"), port, "super-genere-aleatoire", "postgresql-x64-17")


def test_absent_server_is_installed_after_consent_then_provisioned(tmp_path):
    rec = Recorder(installs=[], installed=installed_result(tmp_path))
    cfg = new_cfg()
    ui = HeadlessUI(choice=0)
    pg.ensure_database(cfg, ui, rec.deps())

    assert rec.calls[0] == ("install",)
    [(_, host, port, su, sp, *_rest)] = rec.provisioned()
    assert (port, su, sp) == (5433, "postgres", "super-genere-aleatoire")
    assert cfg.postgres.managed and cfg.postgres.superuser_password == "super-genere-aleatoire"
    assert cfg.postgres.port == 5433 and cfg.postgres.bin_dir.endswith("bin")


def test_absent_server_quit_choice_installs_nothing(tmp_path):
    rec = Recorder(installs=[], installed=installed_result(tmp_path))
    for choice in (2, None):
        with pytest.raises(SetupCancelled):
            pg.ensure_database(new_cfg(), HeadlessUI(choice=choice), rec.deps())
    assert rec.calls == []


def test_absent_server_can_use_an_existing_remote_server(tmp_path):
    rec = Recorder(installs=[], valid_logins={("admin", "pw")})
    cfg = new_cfg()
    ui = HeadlessUI(choice=1, connection={"host": "10.0.0.5", "port": 5440, "user": "admin", "password": "pw"})
    pg.ensure_database(cfg, ui, rec.deps())
    assert ("install",) not in rec.calls
    assert rec.provisioned()[0][1:5] == ("10.0.0.5", 5440, "admin", "pw")
    assert cfg.postgres.host == "10.0.0.5" and cfg.postgres.port == 5440 and not cfg.postgres.managed and cfg.postgres.superuser_password == ""


def test_existing_server_with_bad_credentials_is_refused(tmp_path):
    rec = Recorder(installs=[])
    ui = HeadlessUI(choice=1, connection={"host": "127.0.0.1", "port": 5432, "user": "x", "password": "y"})
    with pytest.raises(pg.PostgresError, match="Connexion refusée"):
        pg.ensure_database(new_cfg(), ui, rec.deps())
    assert not rec.provisioned()


def test_existing_server_dialog_cancelled(tmp_path):
    with pytest.raises(SetupCancelled):
        pg.ensure_database(new_cfg(), HeadlessUI(choice=1, connection=None), Recorder(installs=[]).deps())


# --- détection ----------------------------------------------------------------------------------------------


def test_detection_merges_sources_dedupes_and_sorts_newest_first(tmp_path):
    a, b = fake_install(tmp_path, "16.4", "postgresql-x64-16"), fake_install(tmp_path, "17.10", "postgresql-x64-17")
    registry = lambda: [  # noqa: E731
        {"Base Directory": str(a.bin_dir.parent), "Version": "16.4", "Service ID": "postgresql-x64-16", "Data Directory": r"C:\d16"},
        {"Base Directory": str(b.bin_dir.parent), "Version": "17.10-2", "Service ID": "postgresql-x64-17"},
        {"name": "sans-base"},  # entrée incomplète ignorée
        {"Base Directory": str(tmp_path / "disparu"), "Version": "15"},  # dossier supprimé : ignoré
    ]
    found = pg.detect_installs(registry=registry, scan=lambda: [b.bin_dir.parent, a.bin_dir.parent], which=lambda name: str(b.bin_dir / "psql.exe"))
    assert [i.version for i in found] == ["17.10-2", "16.4"]
    assert found[0].service == "postgresql-x64-17" and found[1].data_dir == Path(r"C:\d16")


def test_detection_with_nothing_installed():
    assert pg.detect_installs(registry=lambda: [], scan=lambda: [], which=lambda name: None) == []


def test_detection_finds_postgres_only_from_path(tmp_path):
    inst = fake_install(tmp_path, "17.5")
    (inst.bin_dir / "psql.exe").write_bytes(b"")
    found = pg.detect_installs(registry=lambda: [], scan=lambda: [], which=lambda name: str(inst.bin_dir / "psql.exe"))
    assert [i.bin_dir for i in found] == [inst.bin_dir]


def test_service_state_parsing():
    class R:
        def __init__(self, out):
            self.stdout = out

    assert pg.service_state("x", run=lambda *a, **k: R("SERVICE_NAME: x\n        STATE              : 4  RUNNING\n")) == "RUNNING"
    assert pg.service_state("x", run=lambda *a, **k: R("        STATE              : 1  STOPPED")) == "STOPPED"
    assert pg.service_state("x", run=lambda *a, **k: R("[SC] EnumQueryServicesStatus:OpenService ÉCHEC 1060")) is None


def test_find_server_port_returns_first_answering_port():
    answering = {5433, 5434}
    assert pg.find_server_port(probe=lambda host, port: port in answering) == 5433
    assert pg.find_server_port(probe=lambda host, port: False) is None


# --- installation silencieuse ---------------------------------------------------------------------------------


def run_install(tmp_path, *, exit_code=0, refuse=False, ready=True, monkeypatch=None):
    captured = {}
    installer = tmp_path / "pg-setup.exe"
    installer.write_bytes(b"MZ")

    def run_installer(exe, args, wait):
        captured.update(exe=exe, args=args, wait=wait)
        option_path = Path(args.split('"')[1])
        captured["option_text"] = option_path.read_text(encoding="ascii")
        captured["option_path"] = option_path
        if refuse:
            raise elevation.ElevationRefused("refusé")
        return exit_code

    monkeypatch.setattr(pg, "looks_like_postgres", lambda host, port: ready)
    ui = HeadlessUI()
    try:
        result = pg.install_postgres(ui, fetch_installer=lambda ui_: installer, run_installer=run_installer,
                                     detect=lambda: [fake_install(tmp_path, "17.12")], sleep=lambda s: None)
    except Exception as exc:  # noqa: BLE001
        captured["error"] = exc
        result = None
    return result, captured


def test_install_passes_options_through_a_file_not_the_command_line(tmp_path, monkeypatch):
    result, captured = run_install(tmp_path, monkeypatch=monkeypatch)
    assert result is not None and result.super_password
    assert result.super_password not in captured["args"]  # le mot de passe n'apparaît pas dans la liste des processus
    text = captured["option_text"]
    for line in ("mode=unattended", "unattendedmodeui=none", f"superpassword={result.super_password}", "disable-components=pgAdmin,stackbuilder"):
        assert line in text
    assert f"serverport={result.port}" in text and "servicename=postgresql-x64-17" in text
    assert captured["wait"] >= 10 * 60 * 1000  # laisse le temps à l'installateur


def test_option_file_with_the_password_is_deleted_afterwards_even_on_failure(tmp_path, monkeypatch):
    _, ok = run_install(tmp_path, monkeypatch=monkeypatch)
    assert not ok["option_path"].exists()
    _, failed = run_install(tmp_path, exit_code=1, monkeypatch=monkeypatch)
    assert not failed["option_path"].exists()


def test_installer_failure_gives_actionable_message(tmp_path, monkeypatch):
    result, captured = run_install(tmp_path, exit_code=1603, monkeypatch=monkeypatch)
    assert result is None and "1603" in str(captured["error"]) and "manuellement" in str(captured["error"])


def test_refused_uac_prompt_is_explained(tmp_path, monkeypatch):
    result, captured = run_install(tmp_path, refuse=True, monkeypatch=monkeypatch)
    assert result is None and "droits administrateur" in str(captured["error"])


def test_server_not_answering_after_install_is_reported(tmp_path, monkeypatch):
    monkeypatch.setattr(pg.net, "wait_until", lambda *a, **k: False)
    result, captured = run_install(tmp_path, ready=False, monkeypatch=monkeypatch)
    assert result is None and "ne répond pas" in str(captured["error"])


def test_option_file_format(tmp_path):
    path = pg.write_option_file(tmp_path, super_password="Abc_123-x", port=5433, service="svc")
    assert path.read_text(encoding="ascii").splitlines()[:4] == ["mode=unattended", "unattendedmodeui=none", "superpassword=Abc_123-x", "serverport=5433"]


def test_installer_download_failure_removes_the_file_and_explains(tmp_path):
    from tjlauncher import download as dl

    def bad_download(url, dest, **kwargs):
        dest.write_bytes(b"x")
        raise dl.DownloadError("empreinte différente")

    with pytest.raises(pg.PostgresError, match="empreinte"):
        pg.ensure_installer(HeadlessUI(), downloader=bad_download, verifier=lambda *a: None)
    assert not any(paths.downloads_dir().iterdir())


def test_installer_is_verified_for_hash_and_signature_before_use(tmp_path):
    from tjlauncher.version import PG_INSTALLER

    seen = {}

    def downloader(url, dest, *, expected_sha256, progress):
        seen["hash"] = expected_sha256
        seen["url"] = url
        dest.write_bytes(b"MZ")
        progress(1, 2)

    def verifier(path, signer):
        seen["signer"] = signer

    path = pg.ensure_installer(HeadlessUI(), downloader=downloader, verifier=verifier)
    assert path.exists() and seen == {"hash": PG_INSTALLER["sha256"], "url": PG_INSTALLER["url"], "signer": "EnterpriseDB Corporation"}
    assert PG_INSTALLER["url"].startswith("https://get.enterprisedb.com/") and len(PG_INSTALLER["sha256"]) == 64


# --- sondage du protocole ---------------------------------------------------------------------------------------


def _serve_once(reply: bytes):
    import socket
    import threading

    server = socket.socket()
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    received = []

    def run():
        conn, _ = server.accept()
        with conn:
            received.append(conn.recv(8))
            if reply:
                conn.sendall(reply)
        server.close()

    threading.Thread(target=run, daemon=True).start()
    return server.getsockname()[1], received


@pytest.mark.parametrize("reply", [b"S", b"N"])
def test_probe_recognises_a_postgres_ssl_negotiation_answer(reply):
    port, received = _serve_once(reply)
    assert pg.looks_like_postgres("127.0.0.1", port)
    assert received == [bytes([0, 0, 0, 8, 4, 210, 22, 47])]  # uniquement la SSLRequest : aucune authentification tentée


@pytest.mark.parametrize("reply", [b"HTTP/1.1 400", b"", b"E"])
def test_probe_rejects_other_services(reply):
    port, _ = _serve_once(reply)
    assert not pg.looks_like_postgres("127.0.0.1", port, timeout=1.0)


def test_probe_rejects_a_closed_port():
    assert not pg.looks_like_postgres("127.0.0.1", 1, timeout=0.5)


def test_a_stale_superuser_password_is_dropped_for_a_server_that_is_not_ours(tmp_path):
    cfg = new_cfg()
    cfg.postgres.managed = False
    cfg.postgres.superuser_password = "perime-d-une-ancienne-config"
    rec = Recorder(installs=[fake_install(tmp_path)], valid_logins={("postgres", "saisi")})
    pg.ensure_database(cfg, HeadlessUI(secret="saisi"), rec.deps())
    assert cfg.postgres.superuser_password == ""  # jamais conservé : ce serveur n'appartient pas à l'application
