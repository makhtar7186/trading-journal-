import boto3
import pytest
from django.core.exceptions import ImproperlyConfigured
from moto import mock_aws
from rest_framework.test import APIClient

from core.storage import get_storage
from core.storage.base import FileNotFoundInStorage, StorageError
from core.storage.local import LocalStorage
from core.storage.s3 import S3Storage

from .conftest import trade_payload
from .image_factory import png_bytes, upload

BUCKET = "trading-test"


# --- stockage local ------------------------------------------------------------------


def test_local_roundtrip(tmp_path):
    storage = LocalStorage(tmp_path)
    storage.save("trades/t1/a.png", b"data", "image/png")
    assert storage.open("trades/t1/a.png").read() == b"data"
    assert storage.signed_url("trades/t1/a.png") is None
    storage.delete("trades/t1/a.png")
    storage.delete("trades/t1/a.png")  # idempotent
    with pytest.raises(FileNotFoundInStorage):
        storage.open("trades/t1/a.png")


def test_local_delete_prunes_empty_directories_but_keeps_root_and_siblings(tmp_path):
    root = tmp_path / "root"
    storage = LocalStorage(root)
    storage.save("trades/t1/a.png", b"1", "image/png")
    storage.save("trades/t1/b.png", b"2", "image/png")
    storage.save("trades/t2/c.png", b"3", "image/png")

    storage.delete("trades/t1/a.png")
    assert (root / "trades/t1").exists()  # b.png y est encore
    storage.delete("trades/t1/b.png")
    assert not (root / "trades/t1").exists()  # dossier vide retiré
    assert (root / "trades/t2/c.png").exists()  # voisin intact
    storage.delete("trades/t2/c.png")
    assert not (root / "trades").exists()
    assert root.exists()  # la racine n'est jamais supprimée


@pytest.mark.parametrize("key", ["../evil.png", "trades/../../evil.png", "/etc/passwd", "a/../../b"])
def test_local_refuses_path_traversal(tmp_path, key):
    root = tmp_path / "root"
    storage = LocalStorage(root)
    with pytest.raises(StorageError):
        storage.save(key, b"x", "image/png")
    with pytest.raises(StorageError):
        storage.open(key)
    assert not (tmp_path / "evil.png").exists()


# --- sélection du backend -------------------------------------------------------------


def test_get_storage_selects_backend(settings):
    settings.STORAGE_BACKEND = "local"
    assert isinstance(get_storage(), LocalStorage)

    settings.STORAGE_BACKEND = "s3"
    settings.S3_BUCKET = ""
    with pytest.raises(ImproperlyConfigured):
        get_storage()

    settings.STORAGE_BACKEND = "ftp"
    with pytest.raises(ImproperlyConfigured):
        get_storage()


# --- S3 (simulé par moto : mêmes appels boto3 que la production) ----------------------------


@pytest.fixture
def s3_bucket():
    with mock_aws():
        client = boto3.client("s3", region_name="us-east-1")
        client.create_bucket(Bucket=BUCKET)
        yield client


@pytest.fixture
def s3_settings(settings, s3_bucket, monkeypatch):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "test")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "test")
    settings.STORAGE_BACKEND = "s3"
    settings.S3_BUCKET = BUCKET
    settings.S3_ENDPOINT_URL = ""
    settings.S3_ACCESS_KEY_ID = "test"
    settings.S3_SECRET_ACCESS_KEY = "test"
    settings.S3_REGION = "us-east-1"


def test_s3_roundtrip_and_signed_url(s3_settings, s3_bucket):
    storage = get_storage()
    assert isinstance(storage, S3Storage)
    storage.save("trades/t1/a.png", b"data", "image/png")
    assert s3_bucket.head_object(Bucket=BUCKET, Key="trades/t1/a.png")["ContentType"] == "image/png"
    assert storage.open("trades/t1/a.png").read() == b"data"

    url = storage.signed_url("trades/t1/a.png", 60)
    assert BUCKET in url
    assert "X-Amz-Signature" in url or "Signature=" in url
    assert "Expires" in url or "X-Amz-Expires=60" in url

    storage.delete("trades/t1/a.png")
    storage.delete("trades/t1/a.png")  # idempotent
    with pytest.raises(FileNotFoundInStorage):
        storage.open("trades/t1/a.png")


def test_s3_write_failure_is_a_storage_error(s3_settings):
    storage = S3Storage(bucket="bucket-inexistant", region_name="us-east-1")
    with pytest.raises(StorageError):
        storage.save("k.png", b"x", "image/png")


@pytest.mark.django_db
def test_screenshots_end_to_end_with_s3(s3_settings, s3_bucket, client_a, django_capture_on_commit_callbacks):
    trade = client_a.post("/api/v1/trades/", trade_payload(), format="json").json()
    response = client_a.post(
        f"/api/v1/trades/{trade['id']}/screenshots/",
        {"files": [upload("s3.png", png_bytes())], "category": "BEFORE"},
        format="multipart",
    )
    assert response.status_code == 201
    shot = response.json()[0]
    assert len(s3_bucket.list_objects_v2(Bucket=BUCKET)["Contents"]) == 1

    # Accès : redirection vers une URL signée de courte durée, jamais de bucket public.
    served = client_a.get(shot["file_url"])
    assert served.status_code == 302
    assert "Signature" in served.headers["Location"]
    assert served.headers["Cache-Control"] == "private, no-store"
    assert APIClient().get(shot["file_url"]).status_code in (401, 403)

    with django_capture_on_commit_callbacks(execute=True):
        assert client_a.delete(f"/api/v1/screenshots/{shot['id']}/").status_code == 204
    assert s3_bucket.list_objects_v2(Bucket=BUCKET).get("KeyCount", 0) == 0
