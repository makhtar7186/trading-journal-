import hashlib
import json
import os
import time
import zipfile
from pathlib import Path

import pytest

from tjlauncher import backup
from tjlauncher.config import Config, PostgresConfig


def cfg_for(tmp_path):
    cfg = Config()
    cfg.postgres = PostgresConfig(password="Pg-Secret-4d8f1c-ZZ", bin_dir=str(tmp_path))
    return cfg


class FakeRun:
    """Imite pg_dump / pg_restore : écrit un dump factice et mémorise les appels."""

    def __init__(self, dump=b"DUMP", fail=False):
        self.calls, self.dump, self.fail = [], dump, fail

    def __call__(self, cmd, env=None, **kwargs):
        self.calls.append((cmd, env))
        if self.fail:
            return type("R", (), {"returncode": 1, "stderr": "boum"})()
        if "-f" in cmd:
            Path(cmd[cmd.index("-f") + 1]).write_bytes(self.dump)
        return type("R", (), {"returncode": 0, "stderr": ""})()


@pytest.fixture
def fake_tools(tmp_path):
    for name in ("pg_dump", "pg_restore"):
        (tmp_path / f"{name}.exe").write_bytes(b"")
    return tmp_path


def make_archive(tmp_path, entries, *, dump=b"DUMP", manifest=None):
    path = tmp_path / "a.tjbackup"
    manifest = manifest if manifest is not None else {"format": 1, "app_version": "1", "created_at": "x", "database": "d",
                                                       "db_sha256": hashlib.sha256(dump).hexdigest(), "db_bytes": len(dump), "storage_files": 0}
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("manifest.json", json.dumps(manifest))
        z.writestr("db.dump", dump)
        for name, data in entries.items():
            z.writestr(name, data)
    return path


def test_password_goes_through_the_environment_never_the_command_line(tmp_path, fake_tools):
    run = FakeRun()
    backup.create_backup(cfg_for(fake_tools), tmp_path / "out.tjbackup", run=run, storage=tmp_path / "none")
    cmd, env = run.calls[0]
    assert env["PGPASSWORD"] == "Pg-Secret-4d8f1c-ZZ" and "Pg-Secret-4d8f1c-ZZ" not in " ".join(cmd)


def test_archive_layout_and_manifest(tmp_path, fake_tools):
    storage = tmp_path / "storage"
    (storage / "trades" / "t1").mkdir(parents=True)
    (storage / "trades" / "t1" / "a.png").write_bytes(b"png")
    out = backup.create_backup(cfg_for(fake_tools), tmp_path / "o.tjbackup", run=FakeRun(b"XYZ"), storage=storage)
    with zipfile.ZipFile(out) as z:
        assert sorted(z.namelist()) == ["db.dump", "manifest.json", "storage/trades/t1/a.png"]
        manifest = json.loads(z.read("manifest.json"))
    assert manifest["db_sha256"] == hashlib.sha256(b"XYZ").hexdigest() and manifest["storage_files"] == 1 and manifest["format"] == 1
    assert backup.verify_backup(out)["storage_files"] == 1
    assert sorted(p.name for p in tmp_path.iterdir()) == ["o.tjbackup", "pg_dump.exe", "pg_restore.exe", "storage"]  # aucun résidu temporaire


def test_failed_dump_leaves_no_file(tmp_path, fake_tools):
    with pytest.raises(backup.BackupError, match="boum"):
        backup.create_backup(cfg_for(fake_tools), tmp_path / "o.tjbackup", run=FakeRun(fail=True), storage=tmp_path)
    assert not (tmp_path / "o.tjbackup").exists()


def test_missing_pg_dump_gives_actionable_error(tmp_path):
    cfg = cfg_for(tmp_path)
    cfg.postgres.bin_dir = str(tmp_path / "vide")
    import shutil

    original = shutil.which
    shutil.which = lambda name: None
    try:
        with pytest.raises(backup.BackupError, match="introuvable"):
            backup.pg_tool(cfg, "pg_dump")
    finally:
        shutil.which = original


# --- intégrité -------------------------------------------------------------------------------------------------


def test_verify_accepts_a_good_archive(tmp_path):
    assert backup.verify_backup(make_archive(tmp_path, {}))["format"] == 1


def test_verify_rejects_tampered_database(tmp_path):
    path = make_archive(tmp_path, {}, dump=b"original")
    with zipfile.ZipFile(path) as z:
        manifest = z.read("manifest.json")
    with zipfile.ZipFile(path, "w") as z:  # dump remplacé, manifeste inchangé
        z.writestr("manifest.json", manifest)
        z.writestr("db.dump", b"modifie")
    with pytest.raises(backup.BackupError, match="empreinte"):
        backup.verify_backup(path)


@pytest.mark.parametrize("content", [b"n'importe quoi", b""])
def test_verify_rejects_non_zip_files(tmp_path, content):
    path = tmp_path / "x.tjbackup"
    path.write_bytes(content)
    with pytest.raises(backup.BackupError):
        backup.verify_backup(path)


def test_verify_rejects_foreign_zip_and_incomplete_archives(tmp_path):
    foreign = tmp_path / "f.zip"
    with zipfile.ZipFile(foreign, "w") as z:
        z.writestr("fichier.txt", "x")
    with pytest.raises(backup.BackupError, match="pas une sauvegarde"):
        backup.verify_backup(foreign)
    with pytest.raises(backup.BackupError, match="incompatible"):
        backup.verify_backup(make_archive(tmp_path, {}, manifest={"format": 99}))
    no_dump = tmp_path / "n.zip"
    with zipfile.ZipFile(no_dump, "w") as z:
        z.writestr("manifest.json", json.dumps({"format": 1}))
    with pytest.raises(backup.BackupError):
        backup.verify_backup(no_dump)


@pytest.mark.parametrize("evil", ["storage/../../evil.txt", "storage/../evil.txt", "storage//abs.txt", "storage/a/../../../x.txt", "storage/C:/win.txt", r"storage/\serveur\partage.txt"])
def test_zip_slip_entries_are_refused_before_anything_changes(tmp_path, fake_tools, evil):
    storage = tmp_path / "storage"
    storage.mkdir()
    (storage / "garde.txt").write_text("intact")
    archive = make_archive(tmp_path, {evil: b"pwned"})
    run = FakeRun()
    with pytest.raises(backup.BackupError, match="dangereuse"):
        backup.restore_backup(cfg_for(fake_tools), archive, run=run, storage=storage, backups=tmp_path / "b")
    assert (storage / "garde.txt").read_text() == "intact"
    assert not (tmp_path / "evil.txt").exists() and not (tmp_path.parent / "evil.txt").exists()
    assert run.calls == []  # rien n'a même été tenté sur la base


def test_safe_target_blocks_traversal(tmp_path):
    root = tmp_path / "r"
    root.mkdir()
    assert backup._safe_target(root, "a/b.png") == (root / "a" / "b.png").resolve()
    for evil in ("../x", "a/../../x", "..\\x"):
        with pytest.raises(backup.BackupError):
            backup._safe_target(root, evil.replace("\\", "/"))


def test_restore_never_overwrites_its_own_source_with_the_safety_backup(tmp_path, fake_tools):
    backups = tmp_path / "b"
    backups.mkdir()
    storage = tmp_path / "storage"
    storage.mkdir()
    run = FakeRun(b"ETAT-ACTUEL")
    src = backup.create_backup(cfg_for(fake_tools), backups / "a.tjbackup", run=run, storage=storage)
    original = src.read_bytes()
    backup.restore_backup(cfg_for(fake_tools), src, run=FakeRun(b"AUTRE-ETAT"), storage=storage, backups=backups)
    assert src.read_bytes() == original  # la source est intacte
    assert len(list(backups.glob("avant-restauration-*"))) == 1


def test_default_names_are_unique_within_the_same_second():
    names = {backup.default_name("x-") for _ in range(50)}
    assert len(names) == 50 and all(n.endswith(backup.EXTENSION) for n in names)


def test_prune_keeps_only_the_most_recent_with_the_prefix(tmp_path):
    for i in range(8):
        p = tmp_path / f"auto-{i}{backup.EXTENSION}"
        p.write_bytes(b"x")
        os.utime(p, (time.time() - (100 - i), time.time() - (100 - i)))
    manual = tmp_path / f"manuel-1{backup.EXTENSION}"
    manual.write_bytes(b"x")
    removed = backup.prune(tmp_path, prefix="auto-", keep=3)
    assert len(removed) == 5
    assert sorted(p.name for p in tmp_path.glob("auto-*")) == [f"auto-5{backup.EXTENSION}", f"auto-6{backup.EXTENSION}", f"auto-7{backup.EXTENSION}"]
    assert manual.exists()  # les sauvegardes manuelles ne sont jamais supprimées


def test_safety_backup_name_collision_with_the_source_is_avoided(tmp_path, fake_tools, monkeypatch):
    """Même si le générateur de noms renvoyait le nom de la source, la sauvegarde de sécurité ne l'écrase pas."""
    backups = tmp_path / "b"
    backups.mkdir()
    storage = tmp_path / "storage"
    storage.mkdir()
    src = backup.create_backup(cfg_for(fake_tools), backups / "avant-restauration-fixe.tjbackup", run=FakeRun(b"ORIGINAL"), storage=storage)
    original = src.read_bytes()
    names = iter(["avant-restauration-fixe.tjbackup", "avant-restauration-fixe.tjbackup", "avant-restauration-autre.tjbackup"])
    monkeypatch.setattr(backup, "default_name", lambda prefix="": next(names))
    safety = backup.restore_backup(cfg_for(fake_tools), src, run=FakeRun(b"NOUVEL-ETAT"), storage=storage, backups=backups)
    assert safety.name == "avant-restauration-autre.tjbackup" and src.read_bytes() == original
