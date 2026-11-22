import uuid
from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps.trades.models import Trade

from .conftest import trade_payload

URL = "/api/v1/trades/"


def create(client, **overrides):
    response = client.post(URL, trade_payload(**overrides), format="json")
    assert response.status_code == 201, response.content
    return response.json()


# --- création et cycle de vie --------------------------------------------------


@pytest.mark.django_db
def test_create_open_trade(client_a, user_a):
    data = create(client_a)
    assert data["status"] == "OPEN"
    assert data["realized_rr"] is None
    assert data["closed_at"] is None
    assert data["asset"] == "EURUSD"  # normalisé en majuscules
    assert Trade.objects.get(pk=data["id"]).user == user_a


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("rr", "status"), [("2.5", "WIN"), ("-1", "LOSS"), ("0", "BE"), ("0.00", "BE")]
)
def test_create_closed_trade_status_derived(client_a, rr, status):
    data = create(client_a, realized_rr=rr)
    assert data["status"] == status
    assert data["closed_at"] is not None


@pytest.mark.django_db
def test_client_cannot_choose_status(client_a):
    data = create(client_a, status="WIN")  # ignoré : lecture seule
    assert data["status"] == "OPEN"
    data = create(client_a, realized_rr="-2", status="WIN")
    assert data["status"] == "LOSS"


@pytest.mark.django_db
def test_close_then_correct_then_reopen(client_a):
    trade = create(client_a)
    url = f"{URL}{trade['id']}/"

    closed = client_a.patch(url, {"realized_rr": "3"}, format="json").json()
    assert closed["status"] == "WIN"
    closed_at = closed["closed_at"]
    assert closed_at is not None

    corrected = client_a.patch(url, {"realized_rr": "-1"}, format="json").json()
    assert corrected["status"] == "LOSS"
    assert corrected["closed_at"] == closed_at  # la date de clôture est conservée

    reopened = client_a.patch(url, {"realized_rr": None}, format="json").json()
    assert reopened["status"] == "OPEN"
    assert reopened["realized_rr"] is None
    assert reopened["closed_at"] is None


@pytest.mark.django_db
def test_patch_without_rr_keeps_result(client_a):
    trade = create(client_a, realized_rr="2")
    patched = client_a.patch(f"{URL}{trade['id']}/", {"notes": "revu"}, format="json").json()
    assert patched["status"] == "WIN"
    assert Decimal(patched["realized_rr"]) == Decimal("2")


@pytest.mark.django_db
def test_closed_at_rejected_on_open_trade(client_a):
    response = client_a.post(
        URL, trade_payload(closed_at="2026-11-10T10:00:00Z"), format="json"
    )
    assert response.status_code == 400
    assert "closed_at" in response.json()


@pytest.mark.django_db
def test_custom_closed_at_is_used(client_a):
    data = create(client_a, realized_rr="1", closed_at="2026-11-10T12:00:00Z")
    assert data["closed_at"].startswith("2026-11-10T12:00:00")


# --- validation ----------------------------------------------------------------


@pytest.mark.django_db
@pytest.mark.parametrize("planned", ["0", "-1", "-0.5"])
def test_planned_rr_must_be_positive(client_a, planned):
    response = client_a.post(URL, trade_payload(planned_rr=planned), format="json")
    assert response.status_code == 400
    assert "planned_rr" in response.json()


@pytest.mark.django_db
def test_required_fields_and_choices(client_a):
    assert client_a.post(URL, {}, format="json").status_code == 400
    assert client_a.post(URL, trade_payload(market_type="STOCKS"), format="json").status_code == 400
    assert client_a.post(URL, trade_payload(direction="LONG"), format="json").status_code == 400
    assert client_a.post(URL, trade_payload(asset="   "), format="json").status_code == 400


@pytest.mark.django_db
def test_rr_is_decimal_not_float(client_a):
    data = create(client_a, realized_rr="1.1", planned_rr="2.2")
    assert data["realized_rr"] == "1.1000"
    assert data["planned_rr"] == "2.2000"


@pytest.mark.django_db
def test_unauthenticated_is_rejected():
    assert APIClient().get(URL).status_code in (401, 403)
    assert APIClient().post(URL, trade_payload(), format="json").status_code in (401, 403)


# --- isolation entre utilisateurs ----------------------------------------------


@pytest.mark.django_db
def test_user_field_from_client_is_ignored(client_a, user_a, user_b):
    data = create(client_a, user=str(user_b.pk), user_id=str(user_b.pk))
    assert Trade.objects.get(pk=data["id"]).user == user_a


@pytest.mark.django_db
def test_other_user_cannot_read_update_or_delete(client_a, client_b):
    trade = create(client_a)
    url = f"{URL}{trade['id']}/"
    assert client_b.get(url).status_code == 404
    assert client_b.patch(url, {"name": "pwned"}, format="json").status_code == 404
    assert client_b.delete(url).status_code == 404
    assert client_a.get(url).json()["name"] == trade["name"]


@pytest.mark.django_db
def test_list_only_returns_own_trades(client_a, client_b):
    create(client_a)
    create(client_a, name="second")
    create(client_b, name="bob trade")
    assert client_a.get(URL).json()["count"] == 2
    assert client_b.get(URL).json()["count"] == 1


@pytest.mark.django_db
def test_cannot_attach_foreign_strategy(client_a, strategy_a, strategy_b):
    assert create(client_a, strategy=str(strategy_a.pk))["strategy"] == str(strategy_a.pk)
    response = client_a.post(URL, trade_payload(strategy=str(strategy_b.pk)), format="json")
    assert response.status_code == 400
    assert "strategy" in response.json()


@pytest.mark.django_db
def test_cannot_patch_in_foreign_strategy(client_a, strategy_b):
    trade = create(client_a)
    response = client_a.patch(
        f"{URL}{trade['id']}/", {"strategy": str(strategy_b.pk)}, format="json"
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_unknown_id_is_404(client_a):
    assert client_a.get(f"{URL}{uuid.uuid4()}/").status_code == 404


@pytest.mark.django_db
def test_delete_trade(client_a):
    trade = create(client_a)
    assert client_a.delete(f"{URL}{trade['id']}/").status_code == 204
    assert Trade.objects.count() == 0


# --- filtres, recherche, tri, pagination ---------------------------------------


@pytest.fixture
def sample(client_a, strategy_a):
    create(client_a, name="A", asset="EURUSD", market_type="FOREX", direction="BUY",
           trade_date="2026-11-01T10:00:00Z", realized_rr="2", strategy=str(strategy_a.pk))
    create(client_a, name="B", asset="XAUUSD", market_type="METALS", direction="SELL",
           trade_date="2026-11-05T10:00:00Z", realized_rr="-1")
    create(client_a, name="C", asset="BTCUSD", market_type="CRYPTO", direction="BUY",
           trade_date="2026-11-10T10:00:00Z")
    create(client_a, name="D", asset="NAS100", market_type="INDICES", direction="BUY",
           trade_date="2026-11-12T10:00:00Z", realized_rr="0")


def names(client, query=""):
    return [t["name"] for t in client.get(f"{URL}?{query}").json()["results"]]


@pytest.mark.django_db
def test_default_order_is_latest_first(client_a, sample):
    assert names(client_a) == ["D", "C", "B", "A"]


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("status=WIN", ["A"]),
        ("status=LOSS", ["B"]),
        ("status=BE", ["D"]),
        ("status=OPEN", ["C"]),
        ("market_type=CRYPTO", ["C"]),
        ("direction=SELL", ["B"]),
        ("asset=xauusd", ["B"]),
        ("date_from=2026-11-05&date_to=2026-11-10", ["C", "B"]),
        ("date_from=2026-11-11", ["D"]),
        ("search=nas", ["D"]),
        ("search=EUR", ["A"]),
        ("ordering=realized_rr&status=WIN", ["A"]),
    ],
)
def test_filters_and_search(client_a, sample, query, expected):
    assert names(client_a, query) == expected


@pytest.mark.django_db
def test_filter_by_strategy(client_a, sample, strategy_a):
    assert names(client_a, f"strategy={strategy_a.pk}") == ["A"]


@pytest.mark.django_db
def test_cannot_filter_with_foreign_strategy(client_a, sample, strategy_b):
    response = client_a.get(f"{URL}?strategy={strategy_b.pk}")
    assert response.status_code == 400


@pytest.mark.django_db
def test_ordering_and_invalid_filter(client_a, sample):
    assert names(client_a, "ordering=trade_date") == ["A", "B", "C", "D"]
    assert client_a.get(f"{URL}?market_type=STOCKS").status_code == 400


@pytest.mark.django_db
def test_pagination(client_a):
    for i in range(25):
        create(client_a, name=f"t{i}", trade_date=f"2026-10-{i + 1:02d}T10:00:00Z")
    page1 = client_a.get(URL).json()
    assert page1["count"] == 25
    assert len(page1["results"]) == 20
    assert page1["next"] is not None
    page2 = client_a.get(URL, {"page": 2}).json()
    assert len(page2["results"]) == 5


@pytest.mark.django_db
def test_page_size_param_is_capped(client_a):
    for i in range(7):
        create(client_a, name=f"t{i}")
    assert len(client_a.get(URL, {"page_size": 5}).json()["results"]) == 5
    assert client_a.get(URL, {"page_size": 100000}).json()["count"] == 7  # plafonné à 100
