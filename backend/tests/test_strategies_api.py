import pytest

from apps.strategies.models import Strategy
from apps.trades.models import Trade

from .conftest import trade_payload

URL = "/api/v1/strategies/"


@pytest.mark.django_db
def test_create_and_owner_is_server_side(client_a, user_a, user_b):
    response = client_a.post(URL, {"name": "Breakout", "user": str(user_b.pk)}, format="json")
    assert response.status_code == 201
    assert Strategy.objects.get(pk=response.json()["id"]).user == user_a
    assert response.json()["is_active"] is True


@pytest.mark.django_db
def test_name_unique_per_user_not_global(client_a, client_b):
    assert client_a.post(URL, {"name": "Breakout"}, format="json").status_code == 201
    assert client_a.post(URL, {"name": "Breakout"}, format="json").status_code == 400
    assert client_b.post(URL, {"name": "Breakout"}, format="json").status_code == 201


@pytest.mark.django_db
def test_blank_name_rejected(client_a):
    assert client_a.post(URL, {"name": "  "}, format="json").status_code == 400


@pytest.mark.django_db
def test_isolation(client_a, client_b, strategy_a):
    url = f"{URL}{strategy_a.pk}/"
    assert client_b.get(url).status_code == 404
    assert client_b.patch(url, {"name": "x"}, format="json").status_code == 404
    assert client_b.delete(url).status_code == 404
    assert client_b.get(URL).json()["count"] == 0
    strategy_a.refresh_from_db()
    assert strategy_a.is_active is True


@pytest.mark.django_db
def test_delete_deactivates_and_keeps_trade_history(client_a, strategy_a):
    trade = client_a.post(
        "/api/v1/trades/", trade_payload(strategy=str(strategy_a.pk)), format="json"
    ).json()
    assert client_a.delete(f"{URL}{strategy_a.pk}/").status_code == 204

    strategy_a.refresh_from_db()
    assert strategy_a.is_active is False
    assert Trade.objects.get(pk=trade["id"]).strategy_id == strategy_a.pk


@pytest.mark.django_db
def test_reactivate_and_filter(client_a, strategy_a):
    client_a.delete(f"{URL}{strategy_a.pk}/")
    assert client_a.get(f"{URL}?is_active=true").json()["count"] == 0
    assert client_a.get(f"{URL}?is_active=false").json()["count"] == 1
    reactivated = client_a.patch(f"{URL}{strategy_a.pk}/", {"is_active": True}, format="json")
    assert reactivated.json()["is_active"] is True
