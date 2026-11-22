"""Intégration RÉELLE : base SQLite créée par Django -> migration vers un vrai PostgreSQL 17 (conteneur jetable).

Les commandes Django (migrate, dumpdata, loaddata, count_rows) tournent comme en production, en processus séparés.
"""
import json
import sqlite3
import uuid

import psycopg
import pytest

from tjlauncher import app, backup, config, dbswitch, paths, runtime
from tjlauncher import postgres as pg
from tjlauncher.config import ENGINE_POSTGRES, ENGINE_SQLITE, Config, PostgresConfig
from tjlauncher.ui import HeadlessUI

SEED = r"""
import uuid
from decimal import Decimal
from django.utils import timezone
from apps.accounts.models import User
from apps.strategies.models import Strategy
from apps.trades.models import Trade
from apps.screenshots.models import TradeScreenshot

user = User.objects.create_user(username="alice", password="Correct-horse-battery-9", timezone="Africa/Dakar")
strat = Strategy.objects.create(user=user, name="Cassure", description="é à ü — accents et « guillemets »", is_active=True)
now = timezone.now()
t1 = Trade.objects.create(user=user, strategy=strat, name="EURUSD long", trade_date=now, market_type="FOREX", asset="EURUSD",
    direction="BUY", planned_rr=Decimal("2.5000"), realized_rr=Decimal("-1.2500"), status="LOSS", closed_at=now,
    entry_price=Decimal("1.08123456"), stop_loss=Decimal("1.07999999"), take_profit=Decimal("1.10000001"), notes="note\nmultiligne ✓")
t2 = Trade.objects.create(user=user, name="BTC", trade_date=now, market_type="CRYPTO", asset="BTCUSD", direction="SELL",
    entry_price=Decimal("67123.45678901"))
Trade.objects.create(user=user, name="Gold BE", trade_date=now, market_type="METALS", asset="XAUUSD", direction="BUY",
    realized_rr=Decimal("0.0000"), status="BE", closed_at=now)
TradeScreenshot.objects.create(trade=t1, storage_key="trades/" + uuid.uuid4().hex + ".png", original_filename="cap.png", category="BEFORE")
print("seeded")
"""


@pytest.fixture
def pg_cfg(pg_server, pg_tools):
    name = f"tj_{uuid.uuid4().hex[:8]}"
    role_password = "role-pass-123_AZ-xyz"
    pg.provision_database(pg_server["host"], pg_server["port"], "postgres", pg_server["super"], name, name, role_password)
    cfg = Config(secret_key="k-integration", db_engine=ENGINE_SQLITE, fallback_reason="test")
    cfg.postgres = PostgresConfig(host=pg_server["host"], port=pg_server["port"], database=name, user=name, password=role_password, bin_dir=pg_tools)
    yield cfg
    with psycopg.connect(host=pg_server["host"], port=pg_server["port"], dbname="postgres", user="postgres", password=pg_server["super"], autocommit=True) as c:
        c.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
        c.execute(f'DROP ROLE IF EXISTS "{name}"')


def pg_conn(cfg):
    p = cfg.postgres
    return psycopg.connect(host=p.host, port=p.port, dbname=p.database, user=p.user, password=p.password, autocommit=True)


@pytest.fixture
def seeded(pg_cfg):
    """SQLite réel, schéma à jour, avec un jeu de données représentatif (décimaux, accents, FK, UUID)."""
    runtime.migrate(pg_cfg)  # moteur sqlite -> crée trading_journal.sqlite3 dans TJ_DATA_DIR
    result = runtime.run_manage(pg_cfg, ["shell", "-c", SEED])
    assert result.returncode == 0 and "seeded" in result.stdout, result.stderr[-800:]
    return pg_cfg


def test_real_migration_copies_everything_exactly(seeded):
    expected = runtime.row_counts(seeded)
    assert expected["trades.Trade"] == 3 and expected["accounts.User"] == 1 and expected["screenshots.TradeScreenshot"] == 1

    copied = dbswitch.migrate_sqlite_to_postgres(seeded, HeadlessUI())
    assert copied == expected

    with pg_conn(seeded) as c:
        assert c.execute("SELECT count(*) FROM trades_trade").fetchone()[0] == 3
        row = c.execute("SELECT entry_price, stop_loss, take_profit, realized_rr, planned_rr, status, notes FROM trades_trade WHERE name = 'EURUSD long'").fetchone()
        assert [str(v) for v in row[:5]] == ["1.08123456", "1.07999999", "1.10000001", "-1.2500", "2.5000"]  # décimaux exacts
        assert row[5] == "LOSS" and row[6] == "note\nmultiligne ✓"
        assert str(c.execute("SELECT entry_price FROM trades_trade WHERE name = 'BTC'").fetchone()[0]) == "67123.45678901"
        assert c.execute("SELECT description FROM strategies_strategy").fetchone()[0] == "é à ü — accents et « guillemets »"
        assert c.execute("SELECT s.original_filename FROM screenshots_tradescreenshot s JOIN trades_trade t ON t.id = s.trade_id WHERE t.name = 'EURUSD long'").fetchone()[0] == "cap.png"
        assert c.execute("SELECT timezone FROM accounts_user").fetchone()[0] == "Africa/Dakar"

    # Les identifiants du compte fonctionnent à l'identique sur PostgreSQL (le hash du mot de passe a été copié tel quel).
    target = Config(secret_key="k", db_engine=ENGINE_POSTGRES, postgres=seeded.postgres)
    check = runtime.run_manage(target, ["shell", "-c",
        "from apps.accounts.models import User; u = User.objects.get(username='alice'); print('OK' if u.check_password('Correct-horse-battery-9') else 'KO')"])
    assert "OK" in check.stdout, check.stderr[-500:]


def test_second_run_after_success_changes_nothing(seeded):
    dbswitch.migrate_sqlite_to_postgres(seeded, HeadlessUI())
    again = dbswitch.migrate_sqlite_to_postgres(seeded, HeadlessUI())  # reprise après interruption : reconnu, pas de doublon
    with pg_conn(seeded) as c:
        assert c.execute("SELECT count(*) FROM trades_trade").fetchone()[0] == 3
    assert again["trades.Trade"] == 3


def test_a_postgres_database_with_other_data_is_never_overwritten(seeded):
    dbswitch.migrate_sqlite_to_postgres(seeded, HeadlessUI())
    with pg_conn(seeded) as c:
        c.execute("DELETE FROM screenshots_tradescreenshot")
        c.execute("DELETE FROM trades_trade WHERE name = 'BTC'")  # PostgreSQL diverge maintenant de SQLite
    with pytest.raises(dbswitch.MigrationError, match="déjà des données différentes"):
        dbswitch.migrate_sqlite_to_postgres(seeded, HeadlessUI())
    with pg_conn(seeded) as c:
        assert c.execute("SELECT count(*) FROM trades_trade").fetchone()[0] == 2  # intact : ni écrasé ni complété


def test_a_failing_import_leaves_postgres_empty_and_sqlite_untouched(seeded, monkeypatch):
    real_load = runtime.load_data

    def corrupt_then_load(cfg, src, run=None):
        text = src.read_text(encoding="utf-8")
        rows = json.loads(text)
        rows.append({"model": "trades.trade", "pk": str(uuid.uuid4()), "fields": {"user": str(uuid.uuid4()), "name": "orphelin"}})  # FK inexistante
        src.write_text(json.dumps(rows), encoding="utf-8")
        real_load(cfg, src)

    ops = dbswitch.Ops(load_data=corrupt_then_load)
    with pytest.raises(dbswitch.MigrationError):
        dbswitch.migrate_sqlite_to_postgres(seeded, HeadlessUI(), ops)
    with pg_conn(seeded) as c:
        assert c.execute("SELECT count(*) FROM trades_trade").fetchone()[0] == 0
        assert c.execute("SELECT count(*) FROM accounts_user").fetchone()[0] == 0
    assert runtime.row_counts(seeded)["trades.Trade"] == 3  # SQLite intact
    assert not list(paths.data_dir().glob("migration-*"))
    assert list(paths.backups_dir().glob("avant-migration-postgresql-*"))  # le filet de sécurité existe


def test_whole_launcher_flow_from_fallback_to_postgres(pg_server, pg_tools, seeded, monkeypatch):
    """Lancement réel : SQLite avec des données -> PostgreSQL devient disponible -> proposition acceptée -> migration."""
    provisioned = seeded.postgres

    def ensure(cfg, ui, deps=None):
        cfg.postgres = provisioned  # « PostgreSQL vient d'être installé et configuré »

    monkeypatch.setattr(pg, "ensure_database", ensure)
    cfg = Config(secret_key="k-integration", db_engine=ENGINE_SQLITE, fallback_reason="pas d'Internet")
    config.save(cfg)
    ui = HeadlessUI(choice=0)

    class NoPg:
        detect = staticmethod(lambda: [])

    launcher = app.Launcher(ui, cfg=cfg, deps=NoPg(), open_url=lambda u: None, online=lambda: True)
    launcher.prepare()

    assert cfg.db_engine == ENGINE_POSTGRES and config.load().db_engine == ENGINE_POSTGRES
    assert not paths.sqlite_path().exists()
    assert list(paths.data_dir().glob("trading_journal.sqlite3.migre-vers-postgresql*"))
    with pg_conn(cfg) as c:
        assert c.execute("SELECT count(*) FROM trades_trade").fetchone()[0] == 3
    # L'application démarre ensuite normalement sur PostgreSQL (migrations idempotentes).
    runtime.migrate(cfg)
    assert runtime.count_users(cfg) == 1
    assert any("Migration terminée" in m for m in ui.messages)


def test_sqlite_file_is_a_normal_database_before_migration(seeded):
    conn = sqlite3.connect(paths.sqlite_path())
    try:
        assert conn.execute("SELECT count(*) FROM trades_trade").fetchone()[0] == 3
    finally:
        conn.close()
    assert backup.database_has_data(seeded)
