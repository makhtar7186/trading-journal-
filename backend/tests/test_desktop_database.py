"""Version desktop : choix du moteur de base (PostgreSQL ou SQLite de secours) et décompte utilisé par la migration."""
import json
import os
import subprocess
import sys
from io import StringIO
from pathlib import Path

import pytest
from django.core.management import call_command

from apps.accounts.models import User
from apps.screenshots.models import TradeScreenshot
from apps.strategies.models import Strategy
from apps.trades.models import Trade

BACKEND = Path(__file__).resolve().parents[1]


def desktop_databases(**env) -> dict:
    """DATABASES de config.settings.desktop dans un processus propre (les réglages sont lus à l'import)."""
    base = {k: v for k, v in os.environ.items() if not k.startswith(("DB_ENGINE", "SQLITE_", "POSTGRES_", "DJANGO_"))}
    base.update(DJANGO_SECRET_KEY="x", POSTGRES_DB="d", POSTGRES_USER="u", POSTGRES_PASSWORD="p", LOG_DIR=str(BACKEND / "logs"), **env)
    code = "import json; from config.settings import desktop as s; print(json.dumps(s.DATABASES['default'], default=str))"
    out = subprocess.run([sys.executable, "-c", code], cwd=BACKEND, env=base, capture_output=True, text=True, check=True)
    return json.loads(out.stdout.strip().splitlines()[-1])


def test_desktop_uses_postgres_by_default():
    assert desktop_databases()["ENGINE"] == "django.db.backends.postgresql"


def test_sqlite_mode_is_selected_by_the_launcher_environment(tmp_path):
    db = desktop_databases(DB_ENGINE="sqlite", SQLITE_PATH=str(tmp_path / "x.sqlite3"))
    assert db["ENGINE"] == "django.db.backends.sqlite3" and db["NAME"] == str(tmp_path / "x.sqlite3")
    assert "journal_mode=WAL" in db["OPTIONS"]["init_command"] and db["OPTIONS"]["transaction_mode"] == "IMMEDIATE"


@pytest.mark.django_db
def test_count_rows_reports_every_business_table():
    user = User.objects.create_user(username="alice", password="Correct-horse-battery-9")
    strategy = Strategy.objects.create(user=user, name="S")
    trade = Trade.objects.create(user=user, strategy=strategy, name="t", trade_date="2026-01-01T00:00:00Z", market_type="FOREX",
                                 asset="EURUSD", direction="BUY")
    TradeScreenshot.objects.create(trade=trade, storage_key="k", original_filename="a.png", category="BEFORE")
    out = StringIO()
    call_command("count_rows", stdout=out)
    assert json.loads(out.getvalue()) == {"accounts.User": 1, "screenshots.TradeScreenshot": 1, "strategies.Strategy": 1, "trades.Trade": 1}
