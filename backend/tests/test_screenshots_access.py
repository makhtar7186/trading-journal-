import pytest
from rest_framework.test import APIClient

from apps.screenshots.models import TradeScreenshot
from apps.trades.models import Trade

from .conftest import trade_payload
from .image_factory import png_bytes, upload


@pytest.fixture
def trade(client_a):
    return client_a.post("/api/v1/trades/", trade_payload(), format="json").json()


@pytest.fixture
def shot(client_a, trade):
    response = client_a.post(
        f"/api/v1/trades/{trade['id']}/screenshots/",
        {"files": [upload("Mon Graphique (1).png", png_bytes((20, 10)))], "category": "AFTER"},
        format="multipart",
    )
    assert response.status_code == 201
    return response.json()[0]


def stored_files(storage_dir):
    return [p for p in storage_dir.rglob("*") if p.is_file()] if storage_dir.exists() else []


# --- liste ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_list_in_upload_order_with_category_filter(client_a, trade):
    url = f"/api/v1/trades/{trade['id']}/screenshots/"
    for name, category in [("a.png", "BEFORE"), ("b.png", "DURING"), ("c.png", "AFTER"), ("d.png", "BEFORE")]:
        client_a.post(url, {"files": [upload(name)], "category": category}, format="multipart")

    assert [s["original_filename"] for s in client_a.get(url).json()] == ["a.png", "b.png", "c.png", "d.png"]
    assert [s["original_filename"] for s in client_a.get(url, {"category": "BEFORE"}).json()] == ["a.png", "d.png"]
    assert client_a.get(url, {"category": "WHATEVER"}).json().__len__() == 4  # filtre inconnu ignoré


# --- accès au fichier ---------------------------------------------------------------


@pytest.mark.django_db
def test_owner_gets_the_file_with_safe_headers(client_a, shot):
    response = client_a.get(shot["file_url"])
    assert response.status_code == 200
    assert response.headers["Content-Type"] == "image/png"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["Cache-Control"].startswith("private")
    disposition = response.headers["Content-Disposition"]
    assert disposition.startswith("inline;")
    assert " " not in disposition.split("filename=")[1].strip('"') and "(" not in disposition
    assert response.getvalue()[:8] == b"\x89PNG\r\n\x1a\n"


@pytest.mark.django_db
def test_file_requires_authentication(shot):
    assert APIClient().get(shot["file_url"]).status_code in (401, 403)


@pytest.mark.django_db
def test_other_user_cannot_access_anything(client_b, trade, shot):
    base = f"/api/v1/screenshots/{shot['id']}/"
    assert client_b.get(f"/api/v1/trades/{trade['id']}/screenshots/").status_code == 404
    post = client_b.post(
        f"/api/v1/trades/{trade['id']}/screenshots/", {"files": [upload()], "category": "BEFORE"}, format="multipart"
    )
    assert post.status_code == 404
    assert client_b.get(base).status_code == 404
    assert client_b.get(base + "file/").status_code == 404
    assert client_b.patch(base, {"category": "DURING"}, format="json").status_code == 404
    assert client_b.delete(base).status_code == 404
    assert TradeScreenshot.objects.count() == 1


@pytest.mark.django_db
def test_missing_file_in_storage_is_404_not_500(client_a, shot, storage_dir):
    for path in stored_files(storage_dir):
        path.unlink()
    assert client_a.get(shot["file_url"]).status_code == 404


# --- modification ---------------------------------------------------------------------


@pytest.mark.django_db
def test_patch_category_and_description_only(client_a, shot, trade):
    url = f"/api/v1/screenshots/{shot['id']}/"
    original_key = TradeScreenshot.objects.get().storage_key
    other_trade = client_a.post("/api/v1/trades/", trade_payload(name="autre"), format="json").json()

    response = client_a.patch(
        url,
        {
            "category": "DURING",
            "description": "Cassure confirmée",
            "trade": other_trade["id"],
            "storage_key": "hack/x.png",
            "original_filename": "pwned.png",
        },
        format="json",
    )
    assert response.status_code == 200
    body = response.json()
    assert (body["category"], body["description"]) == ("DURING", "Cassure confirmée")
    assert body["trade"] == trade["id"]
    assert body["original_filename"] == "Mon Graphique (1).png"
    assert TradeScreenshot.objects.get().storage_key == original_key


@pytest.mark.django_db
def test_patch_validation(client_a, shot):
    url = f"/api/v1/screenshots/{shot['id']}/"
    assert client_a.patch(url, {"category": "NOPE"}, format="json").status_code == 400
    assert client_a.patch(url, {"description": "x" * 501}, format="json").status_code == 400


# --- suppression et nettoyage des fichiers ------------------------------------------------


@pytest.mark.django_db
def test_delete_removes_row_and_file(client_a, shot, storage_dir, django_capture_on_commit_callbacks):
    assert len(stored_files(storage_dir)) == 1
    with django_capture_on_commit_callbacks(execute=True):
        assert client_a.delete(f"/api/v1/screenshots/{shot['id']}/").status_code == 204
    assert TradeScreenshot.objects.count() == 0
    assert stored_files(storage_dir) == []


@pytest.mark.django_db
def test_deleting_a_trade_removes_all_its_files(client_a, trade, storage_dir, django_capture_on_commit_callbacks):
    client_a.post(
        f"/api/v1/trades/{trade['id']}/screenshots/",
        {"files": [upload("1.png"), upload("2.png")], "category": "BEFORE"},
        format="multipart",
    )
    other = client_a.post("/api/v1/trades/", trade_payload(name="garde-moi"), format="json").json()
    client_a.post(
        f"/api/v1/trades/{other['id']}/screenshots/", {"files": [upload("3.png")], "category": "AFTER"}, format="multipart"
    )
    assert len(stored_files(storage_dir)) == 3

    with django_capture_on_commit_callbacks(execute=True):
        assert client_a.delete(f"/api/v1/trades/{trade['id']}/").status_code == 204
    assert Trade.objects.count() == 1
    assert TradeScreenshot.objects.count() == 1
    assert len(stored_files(storage_dir)) == 1  # seul le fichier de l'autre trade subsiste


@pytest.mark.django_db
def test_deleting_the_user_removes_files(user_a, client_a, trade, storage_dir, django_capture_on_commit_callbacks):
    client_a.post(
        f"/api/v1/trades/{trade['id']}/screenshots/", {"files": [upload()], "category": "BEFORE"}, format="multipart"
    )
    with django_capture_on_commit_callbacks(execute=True):
        user_a.delete()
    assert stored_files(storage_dir) == []


@pytest.mark.django_db
def test_file_is_kept_when_the_transaction_rolls_back(client_a, shot, storage_dir, django_capture_on_commit_callbacks):
    from django.db import transaction

    class Boom(Exception):
        pass

    with pytest.raises(Boom), django_capture_on_commit_callbacks(execute=True):
        with transaction.atomic():
            TradeScreenshot.objects.get().delete()
            raise Boom
    assert len(stored_files(storage_dir)) == 1
    assert TradeScreenshot.objects.count() == 1


@pytest.mark.django_db
def test_delete_when_file_already_missing_does_not_fail(client_a, shot, storage_dir, django_capture_on_commit_callbacks):
    for path in stored_files(storage_dir):
        path.unlink()
    with django_capture_on_commit_callbacks(execute=True):
        assert client_a.delete(f"/api/v1/screenshots/{shot['id']}/").status_code == 204
