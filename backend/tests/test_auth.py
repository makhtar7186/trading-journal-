import pytest
from rest_framework.test import APIClient

from .conftest import PASSWORD


def csrf_client():
    """Client qui applique réellement la protection CSRF, comme un navigateur."""
    client = APIClient(enforce_csrf_checks=True)
    client.get("/api/v1/auth/csrf/")
    return client, client.cookies["tj_csrftoken"].value


@pytest.mark.django_db
def test_login_success_sets_http_only_session_cookie(user_a):
    client, token = csrf_client()
    response = client.post(
        "/api/v1/auth/login/",
        {"username": "alice", "password": PASSWORD},
        format="json",
        HTTP_X_CSRFTOKEN=token,
    )
    assert response.status_code == 200
    assert response.json()["username"] == "alice"
    assert "password" not in response.json()
    assert client.cookies["tj_sessionid"]["httponly"]


@pytest.mark.django_db
def test_login_requires_csrf(user_a):
    client = APIClient(enforce_csrf_checks=True)
    response = client.post(
        "/api/v1/auth/login/", {"username": "alice", "password": PASSWORD}, format="json"
    )
    assert response.status_code == 403


@pytest.mark.django_db
def test_login_wrong_password(user_a):
    client, token = csrf_client()
    response = client.post(
        "/api/v1/auth/login/",
        {"username": "alice", "password": "wrong"},
        format="json",
        HTTP_X_CSRFTOKEN=token,
    )
    assert response.status_code == 400
    assert "tj_sessionid" not in client.cookies


@pytest.mark.django_db
def test_login_is_throttled(user_a):
    client, token = csrf_client()
    codes = [
        client.post(
            "/api/v1/auth/login/",
            {"username": "alice", "password": "wrong"},
            format="json",
            HTTP_X_CSRFTOKEN=token,
        ).status_code
        for _ in range(12)
    ]
    assert codes[0] == 400
    assert codes[-1] == 429


@pytest.mark.django_db
def test_me_requires_authentication():
    assert APIClient().get("/api/v1/auth/me/").status_code in (401, 403)


@pytest.mark.django_db
def test_me_and_timezone_update(client_a):
    assert client_a.get("/api/v1/auth/me/").json()["username"] == "alice"
    ok = client_a.patch("/api/v1/auth/me/", {"timezone": "Africa/Dakar"}, format="json")
    assert ok.status_code == 200
    assert ok.json()["timezone"] == "Africa/Dakar"
    bad = client_a.patch("/api/v1/auth/me/", {"timezone": "Mars/Olympus"}, format="json")
    assert bad.status_code == 400


@pytest.mark.django_db
def test_me_cannot_change_username(client_a):
    client_a.patch("/api/v1/auth/me/", {"username": "hacker"}, format="json")
    assert client_a.get("/api/v1/auth/me/").json()["username"] == "alice"


@pytest.mark.django_db
def test_logout_ends_session(user_a):
    client, token = csrf_client()
    client.post(
        "/api/v1/auth/login/",
        {"username": "alice", "password": PASSWORD},
        format="json",
        HTTP_X_CSRFTOKEN=token,
    )
    token = client.cookies["tj_csrftoken"].value
    assert client.get("/api/v1/auth/me/").status_code == 200
    assert client.post("/api/v1/auth/logout/", HTTP_X_CSRFTOKEN=token).status_code == 204
    assert client.get("/api/v1/auth/me/").status_code in (401, 403)
