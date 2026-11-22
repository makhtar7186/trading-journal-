"""Bout en bout sur l'EXÉCUTABLE GELÉ (dist/TradingJournal/tjctl.exe) : PostgreSQL jetable, serveurs réels, requêtes HTTP.

Ignoré si l'exécutable n'est pas construit (build.py) ou si Docker est indisponible.
"""
import http.cookiejar
import io
import json
import os
import re
import subprocess
import threading
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

import psycopg
import pytest

from tjlauncher import config, net
from tjlauncher import postgres as pg

EXE = Path(__file__).resolve().parents[1] / "dist" / "TradingJournal" / "tjctl.exe"
PASSWORD = "Correct-horse-battery-9"
pytestmark = pytest.mark.skipif(not EXE.exists(), reason="exécutable non construit (python build.py)")


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


class Client:
    """Client HTTP minimal avec cookies et protection CSRF, comme un navigateur."""

    def __init__(self, base):
        self.base = base
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar), NoRedirect)

    def cookie(self, name):
        return next((c for c in self.jar if c.name == name), None)

    def request(self, method, path, body=None, headers=None, raw=False):
        headers = dict(headers or {})
        data = None
        if body is not None and not raw:
            data = json.dumps(body).encode()
            headers["Content-Type"] = "application/json"
        elif raw:
            data = body
        if method not in ("GET", "HEAD"):
            token = self.cookie("tj_csrftoken")
            if token:
                headers["X-CSRFToken"] = token.value
        req = urllib.request.Request(self.base + path, data=data, method=method, headers=headers)
        try:
            with self.opener.open(req, timeout=30) as resp:
                return resp.status, resp.read(), dict(resp.headers)
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read(), dict(exc.headers)

    def json(self, method, path, body=None, **kw):
        status, data, headers = self.request(method, path, body, **kw)
        return status, (json.loads(data) if data else None), headers


@pytest.fixture(scope="module")
def app(pg_server, pg_tools, tmp_path_factory):
    data_dir = tmp_path_factory.mktemp("e2e-data")
    db = f"tj_e2e_{uuid.uuid4().hex[:6]}"
    role_pw = "e2e-role-password-123"
    pg.provision_database(pg_server["host"], pg_server["port"], "postgres", pg_server["super"], db, db, role_pw)
    cfg = config.Config(ui_port=49510, api_port=49511)
    cfg.new_secret_key()
    cfg.postgres = config.PostgresConfig(host=pg_server["host"], port=pg_server["port"], database=db, user=db, password=role_pw, bin_dir=pg_tools)
    config.save(cfg, data_dir / "config.json")
    saved = config.load(data_dir / "config.json")

    env = {**os.environ, "TJ_DATA_DIR": str(data_dir), "TJ_ACCOUNT_USER": "e2e_user", "TJ_ACCOUNT_PASSWORD": PASSWORD}
    for name in [k for k in env if k.startswith(("DJANGO_", "POSTGRES_"))]:
        env.pop(name)
    proc = subprocess.Popen([str(EXE), "run", "--no-browser"], env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                            encoding="utf-8", errors="replace", creationflags=0x08000000)
    console: list[str] = []
    threading.Thread(target=lambda: console.extend(proc.stdout), daemon=True).start()  # le tube doit être vidé en continu
    base = saved.ui_url
    # « est prêt » est imprimé APRÈS le démarrage des serveurs ET la création du compte demandé : pas de course.
    ok = net.wait_until(lambda: any("est prêt" in line for line in console) or proc.poll() is not None, timeout=180, interval=0.5)
    if not ok or proc.poll() is not None:
        proc.kill()
        pytest.fail(f"l'application n'a pas démarré (code {proc.poll()}) :\n{''.join(console)[-2000:]}\n{_logs(data_dir)}")
    yield {"proc": proc, "cfg": saved, "base": base, "data": data_dir, "env": env, "db": db, "pg": pg_server, "console": console}
    if proc.poll() is None:
        proc.kill()
    with psycopg.connect(host=pg_server["host"], port=pg_server["port"], dbname="postgres", user="postgres", password=pg_server["super"], autocommit=True) as c:
        c.execute(f'DROP DATABASE IF EXISTS "{db}" WITH (FORCE)')
        c.execute(f'DROP ROLE IF EXISTS "{db}"')


def _logs(data_dir):
    out = []
    for p in sorted((data_dir / "logs").glob("*.log")):
        out.append(f"--- {p.name}\n{p.read_text(encoding='utf-8', errors='replace')[-1500:]}")
    return "\n".join(out)


def login(app, username="e2e_user", password=PASSWORD):
    client = Client(app["base"])
    client.request("GET", "/api/v1/auth/csrf/")
    status, body, _ = client.json("POST", "/api/v1/auth/login/", {"username": username, "password": password})
    assert status == 200, body
    return client


def png():
    from PIL import Image

    out = io.BytesIO()
    Image.new("RGB", (40, 24), (200, 30, 30)).save(out, format="PNG")
    return out.getvalue()


def multipart(fields, files):
    boundary = "----tjboundary" + uuid.uuid4().hex
    body = b""
    for key, value in fields.items():
        body += f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"\r\n\r\n{value}\r\n'.encode()
    for key, (name, content, ctype) in files:
        body += f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"; filename="{name}"\r\nContent-Type: {ctype}\r\n\r\n'.encode() + content + b"\r\n"
    body += f"--{boundary}--\r\n".encode()
    return body, {"Content-Type": f"multipart/form-data; boundary={boundary}"}


# --- démarrage et exposition ------------------------------------------------------------------------------------------


def test_servers_answer_through_the_ui_proxy(app):
    client = Client(app["base"])
    status, body, _ = client.json("GET", "/api/v1/health/")
    assert status == 200 and body == {"status": "ok", "database": "ok"}  # Next → proxy.ts → waitress → Django → PostgreSQL
    assert client.request("GET", "/login")[0] == 200
    assert client.request("GET", "/register")[0] == 200


def test_static_assets_are_served(app):
    client = Client(app["base"])
    _, html, _ = client.request("GET", "/login")
    chunk = re.search(rb'/_next/static/[^"]+\.js', html)
    assert chunk, "aucun chunk JS référencé"
    status, data, headers = client.request("GET", chunk.group(0).decode())
    assert status == 200 and len(data) > 100 and "javascript" in headers.get("Content-Type", "")


def test_security_headers_are_sent(app):
    _, _, headers = Client(app["base"]).request("GET", "/login")
    low = {k.lower(): v for k, v in headers.items()}
    assert low["x-content-type-options"] == "nosniff" and low["x-frame-options"] == "DENY"
    assert low["referrer-policy"] == "same-origin" and "x-powered-by" not in low


def test_servers_listen_on_loopback_only(app):
    out = subprocess.run(["powershell", "-NoProfile", "-Command",
                          f"Get-NetTCPConnection -State Listen -LocalPort {app['cfg'].ui_port},{app['cfg'].api_port} | "
                          "Select-Object -ExpandProperty LocalAddress"], capture_output=True, text=True).stdout.split()
    assert out and set(out) <= {"127.0.0.1"}, f"écoute sur : {out}"  # jamais 0.0.0.0 ni une adresse réseau


def test_backend_port_is_not_the_ui_port_and_both_differ_from_dev_ports(app):
    assert app["cfg"].ui_port != app["cfg"].api_port and {3000, 8000}.isdisjoint({app["cfg"].ui_port, app["cfg"].api_port})


# --- cookies et authentification ---------------------------------------------------------------------------------------


def test_cookies_use_app_specific_names_and_are_http_only(app):
    client = Client(app["base"])
    client.request("GET", "/api/v1/auth/csrf/")
    assert client.cookie("tj_csrftoken") and not client.cookie("csrftoken")
    client.json("POST", "/api/v1/auth/login/", {"username": "e2e_user", "password": PASSWORD})
    session = client.cookie("tj_sessionid")
    assert session is not None and session.has_nonstandard_attr("HttpOnly") and not session.secure  # http local : pas de « Secure »


def test_login_needs_csrf_and_wrong_password_is_refused(app):
    client = Client(app["base"])
    status, body, _ = client.request("POST", "/api/v1/auth/login/", {"username": "e2e_user", "password": PASSWORD})
    assert status == 403 and b"CSRF" in body  # refus par Django (page HTML), pas une réponse JSON
    client.request("GET", "/api/v1/auth/csrf/")
    assert client.json("POST", "/api/v1/auth/login/", {"username": "e2e_user", "password": "faux"})[0] == 400


def test_unauthenticated_api_access_is_refused(app):
    for path in ("/api/v1/trades/", "/api/v1/analytics/overview/", "/api/v1/analytics/calendar/", "/api/v1/auth/me/"):
        assert Client(app["base"]).json("GET", path)[0] in (401, 403), path


# --- création de compte ----------------------------------------------------------------------------------------------


def test_the_account_requested_at_first_launch_exists(app):
    status, me, _ = login(app).json("GET", "/api/v1/auth/me/")
    assert status == 200 and me["username"] == "e2e_user"


def test_registration_is_offered_to_local_visitors_through_the_proxy(app):
    status, body, _ = Client(app["base"]).json("GET", "/api/v1/auth/registration/")
    assert status == 200 and body == {"enabled": True, "has_users": True}


def test_a_remote_visitor_forging_forwarded_for_cannot_register(app):
    spoof = {"X-Forwarded-For": "203.0.113.9"}
    client = Client(app["base"])
    assert client.json("GET", "/api/v1/auth/registration/", headers=spoof)[1]["enabled"] is False
    client.request("GET", "/api/v1/auth/csrf/")
    status, body, _ = client.json("POST", "/api/v1/auth/register/", {"username": "intrus", "password": PASSWORD, "password_confirm": PASSWORD}, headers=spoof)
    assert status == 403
    assert login(app).json("GET", "/api/v1/auth/me/")[1]["username"] == "e2e_user"
    with psycopg.connect(host=app["pg"]["host"], port=app["pg"]["port"], dbname=app["db"], user=app["db"], password=app["cfg"].postgres.password) as c:
        assert c.execute("SELECT count(*) FROM accounts_user WHERE username = 'intrus'").fetchone()[0] == 0


def test_a_new_account_can_be_created_from_the_web_flow(app):
    client = Client(app["base"])
    client.request("GET", "/api/v1/auth/csrf/")
    status, body, _ = client.json("POST", "/api/v1/auth/register/",
                                  {"username": "web_user", "email": "w@example.com", "password": PASSWORD, "password_confirm": PASSWORD, "timezone": "Europe/Paris"})
    assert status == 201 and body["username"] == "web_user" and "password" not in json.dumps(body)
    assert client.json("GET", "/api/v1/auth/me/")[1]["timezone"] == "Europe/Paris"  # connecté par la création
    weak = Client(app["base"])
    weak.request("GET", "/api/v1/auth/csrf/")
    assert weak.json("POST", "/api/v1/auth/register/", {"username": "faible", "password": "12345678", "password_confirm": "12345678"})[0] == 400


# --- fonctionnalités réelles sur la pile gelée ------------------------------------------------------------------------------


def test_trade_lifecycle_screenshot_analytics_and_calendar(app):
    client = login(app, "web_user")
    status, trade, _ = client.json("POST", "/api/v1/trades/", {"name": "Breakout", "trade_date": "2026-11-10T09:30:00Z", "market_type": "FOREX",
                                                               "asset": "eurusd", "direction": "BUY", "planned_rr": "2.5"})
    assert status == 201 and trade["status"] == "OPEN" and trade["asset"] == "EURUSD"
    closed = client.json("PATCH", f"/api/v1/trades/{trade['id']}/", {"realized_rr": "3"})[1]
    assert closed["status"] == "WIN"

    body, headers = multipart({"category": "BEFORE"}, [("files", ("setup.png", png(), "image/png"))])
    status, shots, _ = client.json("POST", f"/api/v1/trades/{trade['id']}/screenshots/", body, headers=headers, raw=True)
    assert status == 201 and len(shots) == 1 and "storage_key" not in shots[0]
    status, img, headers = client.request("GET", shots[0]["file_url"])
    low = {k.lower(): v for k, v in headers.items()}  # le proxy renvoie les noms d'en-têtes en minuscules
    assert status == 200 and img[:8] == b"\x89PNG\r\n\x1a\n" and low["content-type"] == "image/png"
    assert low["x-content-type-options"] == "nosniff" and low["cache-control"].startswith("private")
    assert Client(app["base"]).request("GET", shots[0]["file_url"])[0] in (401, 403)  # image privée
    stored = list((app["data"] / "storage").rglob("*.png"))
    assert len(stored) == 1 and stored[0].is_relative_to(app["data"])  # dans le dossier de données, jamais à côté de l'exécutable

    evil, evil_headers = multipart({"category": "BEFORE"}, [("files", ("x.png", b"<?php system($_GET[1]); ?>", "image/png"))])
    assert client.json("POST", f"/api/v1/trades/{trade['id']}/screenshots/", evil, headers=evil_headers, raw=True)[0] == 400

    overview = client.json("GET", "/api/v1/analytics/overview/")[1]
    assert (overview["closed_trades"], overview["total_r"], overview["win_rate"]) == (1, "3.0000", "100.00") and overview["profit_factor"] is None
    # Clôturé « maintenant » : le calendrier le place à sa date de CLÔTURE (jour dans le fuseau de l'utilisateur, ici Paris).
    from datetime import datetime
    from zoneinfo import ZoneInfo

    closed_day = datetime.fromisoformat(closed["closed_at"].replace("Z", "+00:00")).astimezone(ZoneInfo("Europe/Paris"))
    calendar = client.json("GET", f"/api/v1/analytics/calendar/?month={closed_day:%Y-%m}")[1]
    assert calendar["days"][0]["date"] == f"{closed_day:%Y-%m-%d}" and calendar["summary"]["total_r"] == "3.0000"


def test_openapi_schema_is_available_to_signed_in_users_only(app):
    assert Client(app["base"]).request("GET", "/api/v1/schema/")[0] in (401, 403)
    status, data, _ = login(app).request("GET", "/api/v1/schema/")
    assert status == 200 and b"/api/v1/analytics/calendar/" in data and b"/api/v1/auth/register/" in data


def test_users_are_isolated_in_the_packaged_app(app):
    other = login(app, "e2e_user")
    assert other.json("GET", "/api/v1/trades/")[1]["count"] == 0  # les trades de web_user lui sont invisibles


# --- journaux, sauvegarde et arrêt --------------------------------------------------------------------------------------------


def test_logs_exist_and_never_contain_secrets(app):
    logs = _logs(app["data"])
    assert "backend.log" in logs or "api-process.log" in logs
    secrets_ = [app["cfg"].postgres.password, app["cfg"].secret_key, PASSWORD]
    for log in (app["data"] / "logs").glob("*"):
        text = log.read_text(encoding="utf-8", errors="replace")
        for secret in secrets_:
            assert secret not in text, f"secret trouvé dans {log.name}"


def test_config_file_holds_no_clear_secret(app):
    raw = (app["data"] / "config.json").read_text(encoding="utf-8")
    assert app["cfg"].postgres.password not in raw and app["cfg"].secret_key not in raw


def test_backup_and_verify_while_running(app, tmp_path):
    out = tmp_path / "e2e.tjbackup"
    env = app["env"]
    done = subprocess.run([str(EXE), "backup", str(out)], env=env, capture_output=True, text=True, encoding="utf-8")
    assert done.returncode == 0 and out.exists(), done.stdout + done.stderr
    verified = subprocess.run([str(EXE), "verify", str(out)], env=env, capture_output=True, text=True, encoding="utf-8")
    assert verified.returncode == 0 and "1 capture" in verified.stdout


def test_restore_is_refused_while_the_app_is_running(app, tmp_path):
    out = tmp_path / "r.tjbackup"
    subprocess.run([str(EXE), "backup", str(out)], env=app["env"], capture_output=True)
    done = subprocess.run([str(EXE), "restore", str(out), "--yes"], env=app["env"], capture_output=True, text=True, encoding="utf-8")
    assert done.returncode == 1 and "Fermez" in done.stdout


def test_killing_the_launcher_takes_the_servers_down_with_it(app):
    cfg = app["cfg"]
    assert net.tcp_open("127.0.0.1", cfg.ui_port) and net.tcp_open("127.0.0.1", cfg.api_port)
    app["proc"].kill()  # arrêt brutal du lanceur (plantage, fin de tâche…)
    app["proc"].wait(timeout=10)
    freed = net.wait_until(lambda: not net.tcp_open("127.0.0.1", cfg.ui_port) and not net.tcp_open("127.0.0.1", cfg.api_port), timeout=20, interval=0.5)
    assert freed, "des serveurs orphelins occupent encore les ports"
    time.sleep(0.5)
