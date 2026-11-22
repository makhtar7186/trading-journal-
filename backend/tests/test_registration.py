import io
import json
from unittest.mock import patch

import pytest
from django.core.management import call_command
from django.db import IntegrityError
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.accounts.registration import is_loopback_request

STRONG = "Correct-horse-battery-9"
URL = "/api/v1/auth/register/"
STATUS = "/api/v1/auth/registration/"


@pytest.fixture
def enabled(settings):
    settings.ALLOW_REGISTRATION = True


def csrf_client(**extra):
    client = APIClient(enforce_csrf_checks=True, **extra)
    client.get("/api/v1/auth/csrf/", **extra)
    return client, client.cookies["tj_csrftoken"].value


def register(client, token, **overrides):
    payload = {"username": "nouveau", "password": STRONG, "password_confirm": STRONG}
    payload.update(overrides)
    extra = overrides.pop("_extra", {}) if "_extra" in overrides else {}
    return client.post(URL, payload, format="json", HTTP_X_CSRFTOKEN=token, **extra)


# --- qui peut créer un compte ---------------------------------------------------------


@pytest.mark.django_db
def test_disabled_by_default():
    client, token = csrf_client()
    response = register(client, token)
    assert response.status_code == 403
    assert not User.objects.exists()
    assert APIClient().get(STATUS).json() == {"enabled": False, "has_users": False}


@pytest.mark.django_db
def test_status_reports_enabled_and_existing_accounts(enabled, user_a):
    assert APIClient().get(STATUS).json() == {"enabled": True, "has_users": True}


@pytest.mark.django_db
@pytest.mark.parametrize(
    "extra",
    [
        {"REMOTE_ADDR": "203.0.113.9"},  # connexion distante directe
        {"HTTP_X_FORWARDED_FOR": "203.0.113.9"},  # visiteur distant derrière le proxy local
        {"HTTP_X_FORWARDED_FOR": "127.0.0.1, 198.51.100.4"},  # le dernier maillon est distant
        {"HTTP_X_FORWARDED_FOR": "8.8.8.8, 127.0.0.1"},  # le premier (client réel) est distant
        {"REMOTE_ADDR": "192.168.1.20"},  # réseau local : pas la machine elle-même
        {"HTTP_X_FORWARDED_FOR": "n-importe-quoi"},  # valeur illisible = refus
        {"HTTP_X_FORWARDED_FOR": "::ffff:203.0.113.9"},  # IPv4 distante vue en IPv6
        {"HTTP_X_TJ_FORWARDED": "203.0.113.9"},  # copie, posée par le frontend, de l'en-tête envoyé par le client
        {"HTTP_X_TJ_FORWARDED": "127.0.0.1, 198.51.100.4"},
        {"HTTP_FORWARDED": "for=203.0.113.9;proto=https"},
        {"HTTP_FORWARDED": 'for="[2001:db8::1]:4711"'},
        {"HTTP_FORWARDED": "for=_hidden"},  # nom masqué : aucune adresse lisible = refus
        {"HTTP_X_REAL_IP": "203.0.113.9"},
        {"HTTP_X_FORWARDED_FOR": "127.0.0.1", "HTTP_X_TJ_FORWARDED": "203.0.113.9"},  # le moindre maillon distant suffit
    ],
)
def test_remote_requests_never_register(enabled, extra):
    client, token = csrf_client()
    response = client.post(
        URL, {"username": "intrus", "password": STRONG, "password_confirm": STRONG}, format="json", HTTP_X_CSRFTOKEN=token, **extra
    )
    assert response.status_code == 403
    assert not User.objects.exists()
    assert APIClient().get(STATUS, **extra).json()["enabled"] is False


@pytest.mark.django_db
@pytest.mark.parametrize(
    "extra",
    [
        {},
        {"HTTP_X_FORWARDED_FOR": "127.0.0.1"},
        {"HTTP_X_FORWARDED_FOR": "::1"},
        {"HTTP_X_FORWARDED_FOR": "[::1], 127.0.0.1"},
        {"REMOTE_ADDR": "::1"},
        {"HTTP_X_FORWARDED_FOR": "::ffff:127.0.0.1"},
        {"HTTP_X_FORWARDED_FOR": "127.0.0.1:52000"},
        {"HTTP_FORWARDED": "for=127.0.0.1"},
        {"HTTP_FORWARDED": 'for="[::1]:4711";proto=http'},
        {"HTTP_X_TJ_FORWARDED": "127.0.0.1"},
    ],
)
def test_local_requests_are_accepted(enabled, extra):
    client, token = csrf_client()
    response = client.post(
        URL, {"username": "moi", "password": STRONG, "password_confirm": STRONG}, format="json", HTTP_X_CSRFTOKEN=token, **extra
    )
    assert response.status_code == 201, response.content


def test_is_loopback_request_helper():
    class Req:
        def __init__(self, **meta):
            self.META = meta

    assert is_loopback_request(Req(REMOTE_ADDR="127.0.0.1"))
    assert not is_loopback_request(Req(REMOTE_ADDR=""))
    assert not is_loopback_request(Req())


# --- création ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_creates_an_ordinary_user_and_opens_the_session(enabled):
    client, token = csrf_client()
    response = register(client, token, username="Alice_01", email="alice@example.com", timezone="Africa/Dakar")
    assert response.status_code == 201
    body = response.json()
    assert (body["username"], body["email"], body["timezone"]) == ("Alice_01", "alice@example.com", "Africa/Dakar")
    assert "password" not in json.dumps(body)

    user = User.objects.get(username="Alice_01")
    assert not user.is_staff and not user.is_superuser  # compte ordinaire : pas d'accès à l'administration
    assert user.check_password(STRONG) and user.password != STRONG  # haché
    assert client.get("/api/v1/auth/me/").json()["username"] == "Alice_01"  # connecté


@pytest.mark.django_db
def test_defaults_for_optional_fields(enabled):
    client, token = csrf_client()
    assert register(client, token).status_code == 201
    user = User.objects.get()
    assert (user.email, user.timezone) == ("", "UTC")


@pytest.mark.django_db
def test_csrf_is_required(enabled):
    client = APIClient(enforce_csrf_checks=True)
    response = client.post(URL, {"username": "x1y", "password": STRONG, "password_confirm": STRONG}, format="json")
    assert response.status_code == 403
    assert not User.objects.exists()


@pytest.mark.django_db
def test_username_is_unique_case_insensitively(enabled, user_a):
    client, token = csrf_client()
    for name in ("alice", "ALICE", "Alice"):
        response = register(client, token, username=name)
        assert response.status_code == 400
        assert "username" in response.json()
    assert User.objects.count() == 1


@pytest.mark.django_db
@pytest.mark.parametrize("username", ["ab", "a b c", "nom/avec/slash", "<script>", "", "x" * 151, "tab\tulation"])
def test_invalid_usernames(enabled, username):
    client, token = csrf_client()
    response = register(client, token, username=username)
    assert response.status_code == 400
    assert "username" in response.json()
    assert not User.objects.exists()


@pytest.mark.django_db
@pytest.mark.parametrize(
    "password",
    ["court1A", "password123", "12345678901", "azertyuiop", "nouveau12345"],  # trop court, courant, numérique, similaire à l'identifiant
)
def test_weak_passwords_are_rejected_and_never_echoed(enabled, password):
    client, token = csrf_client()
    response = register(client, token, password=password, password_confirm=password)
    assert response.status_code == 400
    assert "password" in response.json()
    assert password not in response.content.decode()
    assert not User.objects.exists()


@pytest.mark.django_db
def test_password_confirmation_must_match(enabled):
    client, token = csrf_client()
    response = register(client, token, password_confirm=STRONG + "x")
    assert response.status_code == 400
    assert "password_confirm" in response.json()


@pytest.mark.django_db
@pytest.mark.parametrize("extra", [{"email": "pas-un-email"}, {"timezone": "Mars/Olympus"}, {"password": ""}])
def test_other_invalid_fields(enabled, extra):
    client, token = csrf_client()
    assert register(client, token, **extra).status_code == 400
    assert not User.objects.exists()


@pytest.mark.django_db
def test_privilege_fields_cannot_be_injected(enabled):
    client, token = csrf_client()
    response = register(client, token, is_superuser=True, is_staff=True, id="00000000-0000-0000-0000-000000000001")
    assert response.status_code == 201
    user = User.objects.get()
    assert not user.is_superuser and not user.is_staff
    assert str(user.pk) != "00000000-0000-0000-0000-000000000001"


@pytest.mark.django_db
def test_concurrent_duplicate_is_reported_as_a_field_error(enabled):
    client, token = csrf_client()
    with patch.object(User.objects, "create_user", side_effect=IntegrityError("duplicate key")):
        response = register(client, token)
    assert response.status_code == 400
    assert "username" in response.json()


@pytest.mark.django_db
def test_registration_is_rate_limited(enabled):
    client, token = csrf_client()
    codes = [register(client, token, username=f"user{i}", password="x").status_code for i in range(12)]  # mots de passe refusés : sans création
    assert codes[0] == 400
    assert codes[-1] == 429


@pytest.mark.django_db
def test_authenticated_users_can_use_the_app_after_registration(enabled):
    client, token = csrf_client()
    register(client, token)
    token = client.cookies["tj_csrftoken"].value
    created = client.post(
        "/api/v1/trades/",
        {"name": "t", "trade_date": "2026-11-10T09:30:00Z", "market_type": "FOREX", "asset": "EURUSD", "direction": "BUY"},
        format="json",
        HTTP_X_CSRFTOKEN=token,
    )
    assert created.status_code == 201


# --- commandes de gestion (lanceur) -------------------------------------------------------------


def run_register(payload):
    out = io.StringIO()
    with patch("sys.stdin", io.StringIO(json.dumps(payload) if not isinstance(payload, str) else payload)):
        try:
            call_command("register_user", stdout=out)
            code = 0
        except SystemExit as exc:
            code = exc.code
    return code, json.loads(out.getvalue())


@pytest.mark.django_db
def test_register_user_command_creates_an_account_from_stdin():
    code, result = run_register({"username": "desktop", "password": STRONG, "email": "d@example.com"})
    assert code == 0 and result == {"ok": True, "username": "desktop"}
    user = User.objects.get(username="desktop")
    assert user.check_password(STRONG) and not user.is_superuser


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("payload", "field"),
    [
        ({"username": "ab", "password": STRONG}, "username"),
        ({"username": "valide", "password": "faible"}, "password"),
        ({"username": "valide", "password": "password123"}, "password"),
        ({"password": STRONG}, "username"),
    ],
)
def test_register_user_command_refuses_invalid_input(payload, field):
    code, result = run_register(payload)
    assert code == 2 and result["ok"] is False
    assert field in result["errors"]
    assert not User.objects.exists()
    assert STRONG not in json.dumps(result)


@pytest.mark.django_db
@pytest.mark.parametrize("raw", ["pas du json", "[1, 2]", ""])
def test_register_user_command_rejects_malformed_input(raw):
    code, result = run_register(raw)
    assert code == 2 and result["ok"] is False


@pytest.mark.django_db
def test_register_user_command_refuses_duplicates(user_a):
    code, result = run_register({"username": "ALICE", "password": STRONG})
    assert code == 2 and "username" in result["errors"]


@pytest.mark.django_db
def test_count_users_command(user_a, user_b):
    out = io.StringIO()
    call_command("count_users", stdout=out)
    assert out.getvalue().strip() == "2"
