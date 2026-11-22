import json

import pytest

from tjlauncher import config, secrets_store
from tjlauncher.config import Config, PostgresConfig


def test_dpapi_roundtrip_and_ciphertext_is_not_the_secret():
    token = secrets_store.protect("mot de passe é€ très secret")
    assert secrets_store.unprotect(token) == "mot de passe é€ très secret"
    assert "secret" not in token


def test_dpapi_refuses_tampered_or_garbage_values():
    token = secrets_store.protect("x")
    tampered = token[:-6] + ("AAAAAA" if not token.endswith("AAAAAA") else "BBBBBB")
    with pytest.raises(ValueError):
        secrets_store.unprotect(tampered)
    with pytest.raises(ValueError):
        secrets_store.unprotect("pas-du-base64!!")


def test_two_encryptions_of_the_same_secret_differ():
    assert secrets_store.protect("a") != secrets_store.protect("a")


def make():
    cfg = Config(ui_port=48000, api_port=48001, secret_key="clé-secrète-django", last_app_version="1.0.0")
    cfg.postgres = PostgresConfig(host="127.0.0.1", port=5433, password="pg-app-pass", bin_dir=r"C:\pg\bin", service="postgresql-x64-17",
                                  managed=True, superuser_password="pg-super-pass")
    return cfg


def test_config_roundtrip(tmp_path):
    path = tmp_path / "config.json"
    config.save(make(), path)
    loaded = config.load(path)
    assert loaded == make()
    assert loaded.configured and loaded.ui_url == "http://127.0.0.1:48000" and loaded.api_url == "http://127.0.0.1:48001"


def test_secrets_are_never_written_in_clear(tmp_path):
    path = tmp_path / "config.json"
    config.save(make(), path)
    raw = path.read_text(encoding="utf-8")
    for secret in ("clé-secrète-django", "pg-app-pass", "pg-super-pass"):
        assert secret not in raw
    data = json.loads(raw)
    assert data["postgres"]["host"] == "127.0.0.1"  # le non-secret reste lisible
    assert data["postgres"]["password"] and data["secret_key"]


def test_missing_corrupt_or_foreign_config_gives_a_blank_one(tmp_path):
    assert not config.load(tmp_path / "absent.json").configured
    bad = tmp_path / "bad.json"
    bad.write_text("{pas du json", encoding="utf-8")
    assert not config.load(bad).configured
    foreign = tmp_path / "foreign.json"  # secrets chiffrés par un autre compte Windows : illisibles
    data = json.loads(json.dumps({"version": 1, "secret_key": "AAAA", "postgres": {"password": "AAAA"}}))
    foreign.write_text(json.dumps(data), encoding="utf-8")
    assert not config.load(foreign).configured


def test_write_is_atomic_and_leaves_no_temporary_file(tmp_path):
    path = tmp_path / "config.json"
    config.save(make(), path)
    config.save(make(), path)
    assert sorted(p.name for p in tmp_path.iterdir()) == ["config.json"]


def test_unknown_future_fields_are_ignored(tmp_path):
    path = tmp_path / "config.json"
    config.save(make(), path)
    data = json.loads(path.read_text(encoding="utf-8"))
    data["postgres"]["champ_futur"] = 1
    path.write_text(json.dumps(data), encoding="utf-8")
    assert config.load(path).postgres.host == "127.0.0.1"


def test_new_secret_key_is_long_and_random():
    a, b = Config(), Config()
    a.new_secret_key()
    b.new_secret_key()
    assert len(a.secret_key) >= 64 and a.secret_key != b.secret_key
