"""Bout en bout sur l'EXÉCUTABLE GELÉ en mode de secours SQLite (aucun PostgreSQL ni Docker nécessaire).

La proposition de migration est repoussée dans la configuration (upgrade_snooze_until) pour que ce test ne touche JAMAIS
au PostgreSQL éventuellement installé sur la machine de développement.
"""
import os
import subprocess
import threading
from pathlib import Path

import pytest

from tjlauncher import config, net
from test_e2e_frozen import EXE, PASSWORD, Client, _logs

pytestmark = pytest.mark.skipif(not EXE.exists(), reason="exécutable non construit (python build.py)")


def start(data_dir, ui_port):
    env = {**os.environ, "TJ_DATA_DIR": str(data_dir), "TJ_ACCOUNT_USER": "sqlite_user", "TJ_ACCOUNT_PASSWORD": PASSWORD}
    for name in [k for k in env if k.startswith(("DJANGO_", "POSTGRES_", "DB_ENGINE", "SQLITE_"))]:
        env.pop(name)
    proc = subprocess.Popen([str(EXE), "run", "--no-browser"], env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                            encoding="utf-8", errors="replace", creationflags=0x08000000)
    console: list[str] = []
    threading.Thread(target=lambda: console.extend(proc.stdout), daemon=True).start()
    ok = net.wait_until(lambda: any("est prêt" in line for line in console) or proc.poll() is not None, timeout=180, interval=0.5)
    if not ok or proc.poll() is not None:
        proc.kill()
        pytest.fail(f"démarrage impossible (code {proc.poll()}) :\n{''.join(console)[-1500:]}\n{_logs(data_dir)}")
    return proc, env


def cli(env, *args):
    return subprocess.run([str(EXE), *args], env=env, capture_output=True, text=True, encoding="utf-8", timeout=120, creationflags=0x08000000)


def login(base):
    client = Client(base)
    client.request("GET", "/api/v1/auth/csrf/")
    status, body, _ = client.json("POST", "/api/v1/auth/login/", {"username": "sqlite_user", "password": PASSWORD})
    assert status == 200, body
    return client


def test_application_runs_persists_and_backs_up_on_sqlite(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    cfg = config.Config(ui_port=49520, api_port=49521, db_engine="sqlite", fallback_reason="test : pas d'Internet",
                        upgrade_snooze_until="2100-01-01T00:00:00")
    cfg.new_secret_key()
    config.save(cfg, data / "config.json")
    base = config.load(data / "config.json").ui_url

    proc, env = start(data, 49520)
    try:
        assert (data / "trading_journal.sqlite3").exists()
        client = login(base)
        status, strategy, _ = client.json("POST", "/api/v1/strategies/", {"name": "Cassure", "description": "é"})
        assert status == 201, strategy
        trade = {"name": "EURUSD", "trade_date": "2026-11-10T09:30:00Z", "market_type": "FOREX", "asset": "EURUSD", "direction": "BUY",
                 "planned_rr": "2.5", "entry_price": "1.08123456", "strategy": strategy["id"]}
        status, created, _ = client.json("POST", "/api/v1/trades/", trade)
        assert status == 201, created
        status, closed, _ = client.json("PATCH", f"/api/v1/trades/{created['id']}/", {"realized_rr": "-1.25"})
        assert status == 200 and closed["status"] == "LOSS" and closed["entry_price"] == "1.08123456"
        status, overview, _ = client.json("GET", "/api/v1/analytics/overview/")
        assert status == 200 and overview["closed_trades"] == 1

        # Sauvegarde pendant que l'application tourne (base ouverte en WAL) + vérification d'intégrité.
        backup_file = tmp_path / "secours.tjbackup"
        result = cli(env, "backup", str(backup_file))
        assert result.returncode == 0, result.stdout + result.stderr
        verified = cli(env, "verify", str(backup_file))
        assert verified.returncode == 0 and "valide" in verified.stdout
        status_out = cli(env, "status").stdout
        assert "SQLite (mode de secours)" in status_out and "pas d'Internet" in status_out
        # Restauration refusée tant que l'application tourne.
        refused = cli(env, "restore", str(backup_file), "--yes")
        assert refused.returncode == 1 and "Fermez" in refused.stdout
    finally:
        proc.kill()
        proc.wait(timeout=30)

    # Redémarrage : les données et le compte sont toujours là, la configuration n'a pas changé de moteur.
    proc2, env = start(data, 49520)
    try:
        client = login(base)
        status, trades, _ = client.json("GET", "/api/v1/trades/")
        assert status == 200 and trades["count"] == 1 and trades["results"][0]["name"] == "EURUSD"
        assert config.load(data / "config.json").db_engine == "sqlite"
    finally:
        proc2.kill()
        proc2.wait(timeout=30)
