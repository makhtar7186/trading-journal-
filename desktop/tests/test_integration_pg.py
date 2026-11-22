"""Intégration : vrai PostgreSQL 17 (conteneur jetable) + vrais pg_dump / pg_restore (installation locale)."""
import json
import uuid
import zipfile
from pathlib import Path

import psycopg
import pytest

from tjlauncher import backup
from tjlauncher import postgres as pg
from tjlauncher.config import Config, PostgresConfig


@pytest.fixture
def db(pg_server, pg_tools):
    """Base applicative fraîche (nom unique) provisionnée comme le fait le lanceur."""
    name = f"tj_{uuid.uuid4().hex[:8]}"
    role_password = "role-pass-123_AZ-xyz"
    pg.provision_database(pg_server["host"], pg_server["port"], "postgres", pg_server["super"], name, name, role_password)
    cfg = Config(secret_key="k")
    cfg.postgres = PostgresConfig(host=pg_server["host"], port=pg_server["port"], database=name, user=name, password=role_password, bin_dir=pg_tools)
    yield cfg
    with psycopg.connect(host=pg_server["host"], port=pg_server["port"], dbname="postgres", user="postgres", password=pg_server["super"], autocommit=True) as c:
        c.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
        c.execute(f'DROP ROLE IF EXISTS "{name}"')


def connect(cfg):
    pgc = cfg.postgres
    return psycopg.connect(host=pgc.host, port=pgc.port, dbname=pgc.database, user=pgc.user, password=pgc.password, autocommit=True)


# --- provisionnement -----------------------------------------------------------------------------------------


def test_provisioned_role_is_unprivileged_and_owns_only_its_database(db, pg_server):
    with connect(db) as c:
        row = c.execute("SELECT rolsuper, rolcreatedb, rolcreaterole, rolreplication FROM pg_roles WHERE rolname = current_user").fetchone()
        assert row == (False, False, False, False)  # moindre privilège
        assert c.execute("SELECT pg_encoding_to_char(encoding) FROM pg_database WHERE datname = current_database()").fetchone()[0] == "UTF8"
        c.execute("CREATE TABLE ok (id int)")  # propriétaire : peut créer ses tables (migrations Django)
        assert c.execute("SELECT datdba = (SELECT oid FROM pg_roles WHERE rolname = current_user) FROM pg_database WHERE datname = current_database()").fetchone()[0]


def test_role_cannot_create_databases_or_roles_or_read_other_databases(db, pg_server):
    with connect(db) as c:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            c.execute("CREATE DATABASE autre")
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            c.execute("CREATE ROLE pirate SUPERUSER")
    with pytest.raises(psycopg.OperationalError, match="CONNECT privilege"):  # CONNECT retiré à PUBLIC : un autre rôle ne peut pas entrer
        other = "tj_other_" + uuid.uuid4().hex[:6]
        with psycopg.connect(host=pg_server["host"], port=pg_server["port"], dbname="postgres", user="postgres", password=pg_server["super"], autocommit=True) as s:
            s.execute(f"CREATE ROLE {other} LOGIN PASSWORD 'x'")
        try:
            psycopg.connect(host=pg_server["host"], port=pg_server["port"], dbname=db.postgres.database, user=other, password="x").close()
        finally:
            with psycopg.connect(host=pg_server["host"], port=pg_server["port"], dbname="postgres", user="postgres", password=pg_server["super"], autocommit=True) as s:
                s.execute(f"DROP ROLE {other}")


def test_provisioning_is_idempotent_and_keeps_existing_data(db, pg_server):
    with connect(db) as c:
        c.execute("CREATE TABLE precieux (n text)")
        c.execute("INSERT INTO precieux VALUES ('mes trades')")
    old_password = db.postgres.password
    pg.provision_database(pg_server["host"], pg_server["port"], "postgres", pg_server["super"], db.postgres.database, db.postgres.user, "nouveau-mdp")
    assert not pg.can_login(db.postgres.host, db.postgres.port, db.postgres.user, old_password, db.postgres.database)  # ancien mot de passe invalidé
    db.postgres.password = "nouveau-mdp"
    with connect(db) as c:
        assert c.execute("SELECT n FROM precieux").fetchone()[0] == "mes trades"  # données conservées


def test_provisioning_with_a_wrong_superuser_password_fails_cleanly(pg_server):
    with pytest.raises(pg.PostgresError, match="refusée"):
        pg.provision_database(pg_server["host"], pg_server["port"], "postgres", "faux", "x", "x", "x")


def test_identifiers_are_quoted_so_names_cannot_inject_sql(pg_server):
    evil = 'x"; DROP DATABASE postgres; --'
    pg.provision_database(pg_server["host"], pg_server["port"], "postgres", pg_server["super"], evil, evil, "pw'; DROP ROLE postgres; --")
    assert pg.can_login(pg_server["host"], pg_server["port"], evil, "pw'; DROP ROLE postgres; --", evil)
    assert pg.can_login(pg_server["host"], pg_server["port"], "postgres", pg_server["super"])  # le serveur est intact
    with psycopg.connect(host=pg_server["host"], port=pg_server["port"], dbname="postgres", user="postgres", password=pg_server["super"], autocommit=True) as s:
        s.execute(f'DROP DATABASE "{evil.replace(chr(34), chr(34) * 2)}"')
        s.execute(f'DROP ROLE "{evil.replace(chr(34), chr(34) * 2)}"')


def test_server_detection_on_a_real_server(pg_server):
    assert pg.looks_like_postgres(pg_server["host"], pg_server["port"])
    assert pg.find_server_port(pg_server["host"], candidates=range(pg_server["port"] - 1, pg_server["port"] + 2)) == pg_server["port"]
    assert not pg.looks_like_postgres("127.0.0.1", 1)  # rien n'écoute
    assert pg.can_login(pg_server["host"], pg_server["port"], "postgres", pg_server["super"])
    assert not pg.can_login(pg_server["host"], pg_server["port"], "postgres", "mauvais")


# --- sauvegarde / restauration -----------------------------------------------------------------------------------


def fill(cfg, storage: Path, label: str):
    with connect(cfg) as c:
        c.execute("DROP TABLE IF EXISTS trades")
        c.execute("CREATE TABLE trades (id serial PRIMARY KEY, name text)")
        c.execute("INSERT INTO trades (name) VALUES (%s), (%s)", (f"{label}-1", f"{label}-é-2"))
    (storage / "trades" / "t1").mkdir(parents=True, exist_ok=True)
    (storage / "trades" / "t1" / "capture.png").write_bytes(label.encode() * 100)


def names(cfg):
    with connect(cfg) as c:
        return [r[0] for r in c.execute("SELECT name FROM trades ORDER BY id").fetchall()]


def test_backup_then_restore_roundtrip_restores_database_and_files(db, tmp_path):
    storage, backups = tmp_path / "storage", tmp_path / "backups"
    storage.mkdir()
    fill(db, storage, "avant")
    archive = backup.create_backup(db, tmp_path / "save.tjbackup", storage=storage)

    manifest = backup.verify_backup(archive)
    assert manifest["storage_files"] == 1 and manifest["database"] == db.postgres.database and manifest["db_bytes"] > 0

    fill(db, storage, "apres")  # on abîme tout ensuite
    (storage / "trades" / "t1" / "intrus.png").write_bytes(b"x")
    assert names(db) == ["apres-1", "apres-é-2"]

    safety = backup.restore_backup(db, archive, storage=storage, backups=backups)
    assert names(db) == ["avant-1", "avant-é-2"]  # base restaurée (accents compris)
    assert (storage / "trades" / "t1" / "capture.png").read_bytes() == b"avant" * 100
    assert not (storage / "trades" / "t1" / "intrus.png").exists()  # captures remplacées, pas fusionnées
    assert safety.exists() and safety.parent == backups  # sauvegarde de sécurité créée avant
    assert any(p.name.startswith("storage.avant-restauration-") for p in tmp_path.iterdir())  # ancien dossier conservé


def test_safety_backup_contains_the_state_before_the_restore(db, tmp_path):
    storage = tmp_path / "storage"
    storage.mkdir()
    fill(db, storage, "v1")
    archive = backup.create_backup(db, tmp_path / "v1.tjbackup", storage=storage)
    fill(db, storage, "v2")
    safety = backup.restore_backup(db, archive, storage=storage, backups=tmp_path / "b")
    assert names(db) == ["v1-1", "v1-é-2"]
    backup.restore_backup(db, safety, storage=storage, backups=tmp_path / "b")  # on peut revenir en arrière
    assert names(db) == ["v2-1", "v2-é-2"]


def test_failed_restore_leaves_database_and_files_untouched(db, tmp_path):
    storage = tmp_path / "storage"
    storage.mkdir()
    fill(db, storage, "intact")
    good = backup.create_backup(db, tmp_path / "good.tjbackup", storage=storage)

    # Archive dont l'empreinte est cohérente mais dont le dump est inexploitable.
    bad = tmp_path / "bad.tjbackup"
    import hashlib

    garbage = b"ceci n'est pas un dump postgres"
    with zipfile.ZipFile(good) as src, zipfile.ZipFile(bad, "w") as dst:
        manifest = json.loads(src.read("manifest.json"))
        manifest["db_sha256"] = hashlib.sha256(garbage).hexdigest()
        dst.writestr("manifest.json", json.dumps(manifest))
        dst.writestr("db.dump", garbage)
        dst.writestr("storage/trades/t1/capture.png", b"remplacement")

    with pytest.raises(backup.BackupError, match="restauration de la base a échoué"):
        backup.restore_backup(db, bad, storage=storage, backups=tmp_path / "b")
    assert names(db) == ["intact-1", "intact-é-2"]
    assert (storage / "trades" / "t1" / "capture.png").read_bytes() == b"intact" * 100  # captures non remplacées


def test_backup_failure_with_wrong_password_is_reported(db, tmp_path):
    db.postgres.password = "faux"
    with pytest.raises(backup.BackupError, match="sauvegarde de la base a échoué"):
        backup.create_backup(db, tmp_path / "x.tjbackup", storage=tmp_path)
    assert not (tmp_path / "x.tjbackup").exists()  # jamais de fichier à moitié écrit


def test_database_has_data_detection(db):
    assert not backup.database_has_data(db)
    with connect(db) as c:
        c.execute("CREATE TABLE t (i int)")
    assert backup.database_has_data(db)
