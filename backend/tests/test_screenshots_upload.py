import io

import pytest
from PIL import Image

from apps.screenshots.models import TradeScreenshot
from core.storage.base import StorageError
from core.storage.local import LocalStorage

from .conftest import trade_payload
from .image_factory import (
    exif_with_gps_and_orientation,
    gif_bytes,
    jpeg_bytes,
    png_bytes,
    upload,
    webp_bytes,
)


@pytest.fixture
def trade(client_a):
    return client_a.post("/api/v1/trades/", trade_payload(), format="json").json()


def post(client, trade_id, files, category="BEFORE", **extra):
    return client.post(
        f"/api/v1/trades/{trade_id}/screenshots/",
        {"files": files, "category": category, **extra},
        format="multipart",
    )


def stored_files(storage_dir):
    return [p for p in storage_dir.rglob("*") if p.is_file()] if storage_dir.exists() else []


# --- formats acceptés ------------------------------------------------------------


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("name", "content", "ext", "ctype"),
    [
        ("a.png", png_bytes(), "png", "image/png"),
        ("a.jpg", jpeg_bytes(), "jpg", "image/jpeg"),
        ("a.webp", webp_bytes(), "webp", "image/webp"),
    ],
)
def test_upload_valid_image(client_a, trade, storage_dir, name, content, ext, ctype):
    response = post(client_a, trade["id"], [upload(name, content)])
    assert response.status_code == 201, response.content
    [created] = response.json()
    assert created["category"] == "BEFORE"
    assert created["original_filename"] == name
    assert created["file_url"] == f"/api/v1/screenshots/{created['id']}/file/"
    assert "storage_key" not in created  # clé interne jamais exposée
    [path] = stored_files(storage_dir)
    assert path.suffix == f".{ext}"
    assert Image.open(path).format.lower() in ("png", "jpeg", "webp")
    assert client_a.get(created["file_url"]).headers["Content-Type"] == ctype


@pytest.mark.django_db
def test_upload_several_files_in_one_request(client_a, trade, storage_dir):
    response = post(
        client_a, trade["id"], [upload("1.png"), upload("2.jpg", jpeg_bytes()), upload("3.webp", webp_bytes())],
        category="DURING", description="Entrée validée",
    )
    assert response.status_code == 201
    assert len(response.json()) == 3
    assert {s["description"] for s in response.json()} == {"Entrée validée"}
    assert len(stored_files(storage_dir)) == 3


@pytest.mark.django_db
def test_storage_key_is_random_and_filename_is_only_metadata(client_a, trade):
    response = post(client_a, trade["id"], [upload("../../etc/passwd.png")])
    assert response.status_code == 201
    assert response.json()[0]["original_filename"] == "passwd.png"
    key = TradeScreenshot.objects.get().storage_key
    assert key.startswith(f"trades/{trade['id']}/")
    assert ".." not in key and "passwd" not in key


@pytest.mark.django_db
def test_content_type_is_decided_by_content_not_by_client(client_a, trade):
    # PNG déguisé en .jpg avec un Content-Type mensonger : accepté pour ce qu'il est vraiment.
    response = post(client_a, trade["id"], [upload("photo.jpg", png_bytes(), content_type="image/jpeg")])
    assert response.status_code == 201
    assert TradeScreenshot.objects.get().storage_key.endswith(".png")


# --- fichiers refusés -----------------------------------------------------------


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("label", "content", "name"),
    [
        ("texte déguisé en png", b"ceci n'est pas une image", "fake.png"),
        ("script déguisé en png", b"<?php system($_GET['c']); ?>", "shell.png"),
        ("svg", b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>', "x.svg"),
        ("svg déguisé en png", b'<svg xmlns="http://www.w3.org/2000/svg"/>', "x.png"),
        ("gif (format non autorisé)", gif_bytes(), "anim.gif"),
        ("png tronqué", png_bytes(size=(300, 300))[:120], "cut.png"),
        ("html", b"<html><body>hi</body></html>", "page.html"),
    ],
)
def test_non_image_or_forbidden_formats_are_rejected(client_a, trade, storage_dir, label, content, name):
    response = post(client_a, trade["id"], [upload(name, content)])
    assert response.status_code == 400, label
    assert "files" in response.json()
    assert name in response.json()["files"][0]
    assert TradeScreenshot.objects.count() == 0
    assert stored_files(storage_dir) == []


@pytest.mark.django_db
def test_too_large_file_is_rejected(client_a, trade, settings, storage_dir):
    settings.SCREENSHOT_MAX_BYTES = 500
    big = png_bytes(size=(200, 200)) + b"\0" * 1000  # un PNG uni est minuscule : on gonfle le fichier
    assert len(big) > 500
    response = post(client_a, trade["id"], [upload("big.png", big)])
    assert response.status_code == 400
    assert "volumineux" in response.json()["files"][0]
    assert stored_files(storage_dir) == []


@pytest.mark.django_db
def test_decompression_bomb_is_rejected_cheaply(client_a, trade, storage_dir):
    # Quelques Ko sur le disque mais 400 millions de pixels une fois décodé.
    out = io.BytesIO()
    Image.new("1", (20000, 20000)).save(out, format="PNG")
    assert len(out.getvalue()) < 1_000_000
    response = post(client_a, trade["id"], [upload("bomb.png", out.getvalue())])
    assert response.status_code == 400
    assert "dimensions" in response.json()["files"][0]
    assert stored_files(storage_dir) == []


@pytest.mark.django_db
def test_application_pixel_limit_is_enforced(client_a, trade, settings, storage_dir):
    # Limite propre à l'application (indépendante de celle, plus large, de Pillow).
    settings.SCREENSHOT_MAX_PIXELS = 1000
    assert post(client_a, trade["id"], [upload("ok.png", png_bytes(size=(30, 30)))]).status_code == 201
    response = post(client_a, trade["id"], [upload("big.png", png_bytes(size=(100, 100)))])
    assert response.status_code == 400
    assert "dimensions" in response.json()["files"][0]


@pytest.mark.django_db
def test_trailing_payload_is_stripped_by_reencoding(client_a, trade, storage_dir):
    marker = b"<?php evil(); ?>"
    response = post(client_a, trade["id"], [upload("poly.png", png_bytes() + marker)])
    assert response.status_code == 201
    [path] = stored_files(storage_dir)
    assert marker not in path.read_bytes()


@pytest.mark.django_db
def test_exif_metadata_is_removed_and_orientation_applied(client_a, trade, storage_dir):
    raw = jpeg_bytes(size=(10, 20), exif=exif_with_gps_and_orientation(orientation=6))
    assert len(Image.open(io.BytesIO(raw)).getexif()) > 0  # le fichier source contient bien de l'EXIF
    assert post(client_a, trade["id"], [upload("photo.jpg", raw, "image/jpeg")]).status_code == 201

    [path] = stored_files(storage_dir)
    stored = Image.open(path)
    assert len(stored.getexif()) == 0
    assert b"AppareilSecret" not in path.read_bytes()
    assert stored.size == (20, 10)  # orientation 6 (rotation 90°) appliquée avant suppression


@pytest.mark.django_db
def test_cmyk_jpeg_is_converted(client_a, trade):
    out = io.BytesIO()
    Image.new("CMYK", (10, 10), (0, 0, 0, 0)).save(out, format="JPEG")
    assert post(client_a, trade["id"], [upload("cmyk.jpg", out.getvalue())]).status_code == 201


# --- atomicité ---------------------------------------------------------------------


@pytest.mark.django_db
def test_one_bad_file_rejects_the_whole_batch(client_a, trade, storage_dir):
    response = post(client_a, trade["id"], [upload("ok.png"), upload("bad.png", b"nope")])
    assert response.status_code == 400
    assert response.json()["files"] == ["bad.png : Fichier illisible ou corrompu : ce n'est pas une image valide."]
    assert TradeScreenshot.objects.count() == 0
    assert stored_files(storage_dir) == []


@pytest.mark.django_db
def test_storage_failure_rolls_back_everything(client_a, trade, storage_dir, monkeypatch):
    original = LocalStorage.save
    calls = {"n": 0}

    def flaky(self, key, content, content_type):
        calls["n"] += 1
        if calls["n"] == 2:
            raise StorageError("disque plein")
        return original(self, key, content, content_type)

    monkeypatch.setattr(LocalStorage, "save", flaky)
    response = post(client_a, trade["id"], [upload("1.png"), upload("2.png"), upload("3.png")])

    assert response.status_code == 503
    assert TradeScreenshot.objects.count() == 0
    assert stored_files(storage_dir) == []  # le 1er fichier, déjà écrit, a été nettoyé


# --- champs et limites -----------------------------------------------------------


@pytest.mark.django_db
@pytest.mark.parametrize("category", ["", "NOPE", "before"])
def test_invalid_category(client_a, trade, category):
    response = post(client_a, trade["id"], [upload()], category=category)
    assert response.status_code == 400
    assert "category" in response.json()


@pytest.mark.django_db
def test_missing_files_and_too_many_files(client_a, trade, settings):
    assert post(client_a, trade["id"], []).status_code == 400
    settings.SCREENSHOT_MAX_FILES_PER_REQUEST = 2
    response = post(client_a, trade["id"], [upload("1.png"), upload("2.png"), upload("3.png")])
    assert response.status_code == 400
    assert "files" in response.json()


@pytest.mark.django_db
def test_description_too_long(client_a, trade):
    assert post(client_a, trade["id"], [upload()], description="x" * 501).status_code == 400


@pytest.mark.django_db
def test_upload_is_not_possible_unauthenticated(trade):
    from rest_framework.test import APIClient

    assert post(APIClient(), trade["id"], [upload()]).status_code in (401, 403)
