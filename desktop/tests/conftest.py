import os
import shutil
import subprocess
import time
import uuid
from pathlib import Path

import pytest

PG_BIN = Path(r"C:\Program Files\PostgreSQL\17\bin")
SUPER = "su-test-password"


@pytest.fixture(autouse=True)
def isolated_data_dir(tmp_path, monkeypatch):
    """Aucun test ne touche au vrai dossier de données de l'utilisateur."""
    data = tmp_path / "TradingJournalData"
    monkeypatch.setenv("TJ_DATA_DIR", str(data))
    return data


@pytest.fixture(scope="session")
def pg_server():
    """PostgreSQL 17 JETABLE (conteneur Docker, port 55432) pour les tests d'intégration ; ignoré s'il est indisponible."""
    if not shutil.which("docker"):
        pytest.skip("Docker indisponible")
    if subprocess.run(["docker", "info"], capture_output=True).returncode != 0:
        pytest.skip("Docker non démarré")
    name = f"tj-test-pg-{uuid.uuid4().hex[:6]}"
    port = 55432
    started = subprocess.run(
        ["docker", "run", "-d", "--rm", "--name", name, "-e", f"POSTGRES_PASSWORD={SUPER}", "-p", f"127.0.0.1:{port}:5432", "postgres:17-alpine"],
        capture_output=True, text=True,
    )
    if started.returncode != 0:
        pytest.skip(f"Impossible de lancer PostgreSQL : {started.stderr[-200:]}")
    import psycopg

    for _ in range(60):
        try:
            psycopg.connect(host="127.0.0.1", port=port, user="postgres", password=SUPER, dbname="postgres", connect_timeout=2).close()
            break
        except psycopg.Error:
            time.sleep(1)
    else:
        subprocess.run(["docker", "rm", "-f", name], capture_output=True)
        pytest.skip("PostgreSQL de test non prêt")
    yield {"host": "127.0.0.1", "port": port, "super": SUPER}
    subprocess.run(["docker", "rm", "-f", name], capture_output=True)


@pytest.fixture(scope="session")
def pg_tools():
    if not (PG_BIN / "pg_dump.exe").exists():
        pytest.skip("pg_dump.exe introuvable")
    return str(PG_BIN)


def env_without(*names):
    return {k: v for k, v in os.environ.items() if k not in names}
