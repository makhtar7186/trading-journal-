from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps.strategies.models import Strategy
from apps.trades.models import Trade
from apps.trades.services import derive_status

BASE = datetime(2026, 11, 2, 12, 0, tzinfo=UTC)


def closed(user, rr, hours=0, *, asset="EURUSD", market="FOREX", strategy=None, closed_at=None, name=None):
    """Crée un trade clôturé (statut dérivé comme le fait le backend)."""
    when = closed_at or BASE + timedelta(hours=hours)
    return Trade.objects.create(
        user=user,
        name=name or f"{asset} {rr}",
        trade_date=when - timedelta(hours=2),
        market_type=market,
        asset=asset,
        direction="BUY",
        status=derive_status(Decimal(str(rr))),
        realized_rr=Decimal(str(rr)),
        closed_at=when,
        strategy=strategy,
    )


def opened(user, *, asset="EURUSD", market="FOREX", strategy=None):
    return Trade.objects.create(
        user=user, name="ouvert", trade_date=BASE, market_type=market, asset=asset, direction="BUY", strategy=strategy
    )


@pytest.fixture
def dataset_a(user_a):
    """Jeu de données A (voir test_analytics_stats.py) : 8 trades clôturés, total 4,5 R."""
    for i, rr in enumerate([2, 3, 0, 1, -1, -1, 1.5, -1], start=1):
        closed(user_a, rr, hours=i)


def get(client, name, **params):
    return client.get(f"/api/v1/analytics/{name}/", params)


# --- overview ---------------------------------------------------------------------


@pytest.mark.django_db
def test_overview_matches_hand_computed_values(client_a, dataset_a):
    data = get(client_a, "overview").json()
    assert data == {
        "closed_trades": 8,
        "wins": 4,
        "losses": 3,
        "break_even": 1,
        "open_trades": 0,
        "win_rate": "57.14",
        "average_realized_rr": "0.5625",
        "expectancy_r": "0.5625",
        "profit_factor": "2.5000",
        "total_r": "4.5000",
    }


@pytest.mark.django_db
def test_decimals_are_serialized_as_strings_not_floats(client_a, dataset_a):
    data = get(client_a, "overview").json()
    assert all(isinstance(data[k], str) for k in ("win_rate", "expectancy_r", "profit_factor", "total_r"))


@pytest.mark.django_db
def test_open_trades_are_excluded_from_performance_but_counted(client_a, user_a, dataset_a):
    opened(user_a)
    opened(user_a)
    data = get(client_a, "overview").json()
    assert data["open_trades"] == 2
    assert data["closed_trades"] == 8  # inchangé
    assert data["total_r"] == "4.5000"
    assert len(get(client_a, "equity-curve").json()["points"]) == 8


@pytest.mark.django_db
def test_empty_journal_returns_undefined_not_zero(client_a):
    data = get(client_a, "overview").json()
    assert data["closed_trades"] == 0
    for key in ("win_rate", "average_realized_rr", "expectancy_r", "profit_factor", "total_r"):
        assert data[key] is None, key
    assert get(client_a, "equity-curve").json() == {"trades": 0, "total_r": None, "points": []}
    assert get(client_a, "by-asset").json() == {"groups": []}
    assert get(client_a, "by-period").json() == {"granularity": "month", "periods": []}
    perf = get(client_a, "performance").json()
    assert perf["best_trade"] is None and perf["average_win_r"] is None
    assert perf["streaks"] == {"max_win": 0, "max_loss": 0, "current_type": None, "current_length": 0}


@pytest.mark.django_db
def test_profit_factor_is_null_without_losses(client_a, user_a):
    closed(user_a, 2, 1)
    closed(user_a, 1, 2)
    data = get(client_a, "overview").json()
    assert data["profit_factor"] is None
    assert data["win_rate"] == "100.00"


@pytest.mark.django_db
def test_only_break_even_trades(client_a, user_a):
    closed(user_a, 0, 1)
    data = get(client_a, "overview").json()
    assert data["win_rate"] is None  # aucun WIN ni LOSS
    assert data["expectancy_r"] == "0.0000"  # mais l'espérance est définie
    assert data["profit_factor"] is None


# --- performance -------------------------------------------------------------------


@pytest.mark.django_db
def test_performance_details(client_a, dataset_a):
    data = get(client_a, "performance").json()
    assert data["gross_profit_r"] == "7.5000"
    assert data["gross_loss_r"] == "-3.0000"
    assert data["average_win_r"] == "1.8750"
    assert data["average_loss_r"] == "-1.0000"
    assert data["best_trade"]["realized_rr"] == "3.0000"
    assert data["worst_trade"]["realized_rr"] == "-1.0000"
    assert data["streaks"] == {"max_win": 3, "max_loss": 2, "current_type": "LOSS", "current_length": 1}


# --- courbe de performance ------------------------------------------------------------


@pytest.mark.django_db
def test_equity_curve_values(client_a, dataset_a):
    data = get(client_a, "equity-curve").json()
    assert [p["cumulative_r"] for p in data["points"]] == [
        "2.0000", "5.0000", "5.0000", "6.0000", "5.0000", "4.0000", "5.5000", "4.5000"
    ]
    assert [p["realized_rr"] for p in data["points"]][:3] == ["2.0000", "3.0000", "0.0000"]
    assert data["total_r"] == "4.5000"
    assert data["trades"] == 8


@pytest.mark.django_db
def test_equity_curve_order_is_stable_with_identical_close_dates(client_a, user_a):
    same = BASE
    first = closed(user_a, 1, closed_at=same, name="un")
    second = closed(user_a, 2, closed_at=same, name="deux")
    third = closed(user_a, 3, closed_at=same, name="trois")
    expected = [t.name for t in sorted([first, second, third], key=lambda t: (t.closed_at, t.created_at, t.pk))]
    for _ in range(3):  # même résultat à chaque appel
        assert [p["name"] for p in get(client_a, "equity-curve").json()["points"]] == expected


# --- regroupements -------------------------------------------------------------------


@pytest.mark.django_db
def test_by_asset_and_market(client_a, user_a):
    closed(user_a, 2, 1, asset="XAUUSD", market="METALS")
    closed(user_a, -1, 2, asset="XAUUSD", market="METALS")
    closed(user_a, 1, 3, asset="EURUSD", market="FOREX")
    assets = get(client_a, "by-asset").json()["groups"]
    # Les deux actifs valent 1 R : égalité départagée par ordre alphabétique de la clé.
    assert [(g["key"], g["trades"], g["total_r"]) for g in assets] == [("EURUSD", 1, "1.0000"), ("XAUUSD", 2, "1.0000")]
    eur, xau = assets
    assert eur["profit_factor"] is None  # EURUSD : aucune perte
    assert xau["win_rate"] == "50.00" and xau["profit_factor"] == "2.0000"

    markets = get(client_a, "by-market").json()["groups"]
    assert {g["key"]: g["label"] for g in markets} == {"METALS": "Métaux", "FOREX": "Forex"}


@pytest.mark.django_db
def test_by_strategy_names_and_unassigned(client_a, user_a, strategy_a):
    closed(user_a, 2, 1, strategy=strategy_a)
    closed(user_a, 1, 2)
    groups = {g["label"]: g for g in get(client_a, "by-strategy").json()["groups"]}
    assert groups["Breakout"]["key"] == str(strategy_a.pk) and groups["Breakout"]["total_r"] == "2.0000"
    assert groups["Sans stratégie"]["key"] is None


@pytest.mark.django_db
def test_by_period_granularities(client_a, user_a):
    closed(user_a, 1, closed_at=datetime(2026, 11, 9, 10, tzinfo=UTC))  # lundi
    closed(user_a, -1, closed_at=datetime(2026, 11, 11, 10, tzinfo=UTC))  # mercredi, même semaine
    closed(user_a, 2, closed_at=datetime(2026, 12, 1, 10, tzinfo=UTC))

    month = get(client_a, "by-period").json()  # défaut : mois
    assert month["granularity"] == "month"
    assert [(p["period"], p["trades"], p["total_r"]) for p in month["periods"]] == [
        ("2026-11", 2, "0.0000"),
        ("2026-12", 1, "2.0000"),
    ]
    week = get(client_a, "by-period", granularity="week").json()["periods"]
    assert [p["period"] for p in week] == ["2026-11-09", "2026-11-30"]
    day = get(client_a, "by-period", granularity="day").json()["periods"]
    assert [p["period"] for p in day] == ["2026-11-09", "2026-11-11", "2026-12-01"]
    assert get(client_a, "by-period", granularity="year").status_code == 400


# --- filtres : appliqués AVANT les agrégations --------------------------------------------


@pytest.mark.django_db
def test_filters_are_applied_before_aggregation(client_a, user_a, strategy_a):
    closed(user_a, 2, 1, asset="XAUUSD", market="METALS", strategy=strategy_a)
    closed(user_a, -1, 2, asset="EURUSD", market="FOREX")
    closed(user_a, -1, 3, asset="EURUSD", market="FOREX")

    all_data = get(client_a, "overview").json()
    assert all_data["win_rate"] == "33.33"

    gold = get(client_a, "overview", market_type="METALS").json()
    assert (gold["closed_trades"], gold["win_rate"], gold["total_r"]) == (1, "100.00", "2.0000")

    eur = get(client_a, "overview", asset="eurusd").json()  # insensible à la casse
    assert (eur["closed_trades"], eur["win_rate"], eur["total_r"]) == (2, "0.00", "-2.0000")

    by_strategy = get(client_a, "overview", strategy=str(strategy_a.pk)).json()
    assert by_strategy["closed_trades"] == 1
    no_strategy = get(client_a, "overview", strategy="none").json()
    assert no_strategy["closed_trades"] == 2

    combined = get(client_a, "overview", market_type="FOREX", strategy=str(strategy_a.pk)).json()
    assert combined["closed_trades"] == 0 and combined["win_rate"] is None

    assert len(get(client_a, "equity-curve", asset="XAUUSD").json()["points"]) == 1
    assert [g["key"] for g in get(client_a, "by-asset", market_type="FOREX").json()["groups"]] == ["EURUSD"]


@pytest.mark.django_db
def test_date_filters_use_close_date_inclusive_bounds(client_a, user_a):
    closed(user_a, 1, closed_at=datetime(2026, 11, 9, 0, 0, tzinfo=UTC))  # début du jour
    closed(user_a, 1, closed_at=datetime(2026, 11, 10, 23, 59, tzinfo=UTC))  # fin du jour
    closed(user_a, 1, closed_at=datetime(2026, 11, 11, 0, 0, tzinfo=UTC))

    def count(**params):
        return get(client_a, "overview", **params).json()["closed_trades"]

    assert count(date_from="2026-11-09", date_to="2026-11-10") == 2  # les deux bornes incluses
    assert count(date_from="2026-11-10") == 2
    assert count(date_to="2026-11-09") == 1
    assert count(date_from="2026-11-12") == 0


@pytest.mark.django_db
def test_date_filters_follow_the_user_timezone(client_a, user_a):
    user_a.timezone = "Europe/Paris"  # UTC+1 en novembre
    user_a.save()
    closed(user_a, 1, closed_at=datetime(2026, 11, 10, 23, 30, tzinfo=UTC))  # = 11 nov. 00:30 à Paris

    def count(**params):
        return get(client_a, "overview", **params).json()["closed_trades"]

    assert count(date_to="2026-11-10") == 0
    assert count(date_from="2026-11-11", date_to="2026-11-11") == 1
    day = get(client_a, "by-period", granularity="day").json()["periods"]
    assert day[0]["period"] == "2026-11-11"


@pytest.mark.django_db
def test_open_count_ignores_period_but_respects_other_filters(client_a, user_a):
    opened(user_a, market="FOREX")
    opened(user_a, market="CRYPTO", asset="BTCUSD")
    assert get(client_a, "overview").json()["open_trades"] == 2
    assert get(client_a, "overview", market_type="CRYPTO").json()["open_trades"] == 1
    assert get(client_a, "overview", date_from="2030-01-01").json()["open_trades"] == 2


@pytest.mark.django_db
@pytest.mark.parametrize(
    "params",
    [
        {"market_type": "STOCKS"},
        {"date_from": "pas-une-date"},
        {"date_from": "2026-12-01", "date_to": "2026-11-01"},
        {"strategy": "abc"},
        {"strategy": "00000000-0000-0000-0000-000000000000"},
    ],
)
def test_invalid_filters_are_rejected(client_a, params):
    for endpoint in ("overview", "performance", "equity-curve", "by-asset", "by-market", "by-strategy", "by-period"):
        assert get(client_a, endpoint, **params).status_code == 400, endpoint


# --- isolation et accès --------------------------------------------------------------------


@pytest.mark.django_db
def test_statistics_never_include_another_users_trades(client_a, client_b, user_a, user_b, dataset_a):
    closed(user_b, 100, 1, asset="XAUUSD", market="METALS")
    opened(user_b)
    data = get(client_a, "overview").json()
    assert data["closed_trades"] == 8 and data["total_r"] == "4.5000" and data["open_trades"] == 0
    assert "XAUUSD" not in [g["key"] for g in get(client_a, "by-asset").json()["groups"]]
    other = get(client_b, "overview").json()
    assert (other["closed_trades"], other["total_r"], other["open_trades"]) == (1, "100.0000", 1)


@pytest.mark.django_db
def test_cannot_filter_by_another_users_strategy(client_a, strategy_b):
    assert get(client_a, "overview", strategy=str(strategy_b.pk)).status_code == 400


@pytest.mark.django_db
@pytest.mark.parametrize(
    "endpoint", ["overview", "performance", "equity-curve", "by-asset", "by-market", "by-strategy", "by-period"]
)
def test_requires_authentication(endpoint):
    assert get(APIClient(), endpoint).status_code in (401, 403)


@pytest.mark.django_db
def test_reopened_trade_leaves_the_statistics(client_a, user_a):
    trade = closed(user_a, 2, 1)
    assert get(client_a, "overview").json()["closed_trades"] == 1
    client_a.patch(f"/api/v1/trades/{trade.pk}/", {"realized_rr": None}, format="json")
    data = get(client_a, "overview").json()
    assert (data["closed_trades"], data["open_trades"], data["total_r"]) == (0, 1, None)


@pytest.mark.django_db
def test_a_deleted_strategy_label_is_explicit(client_a, user_a):
    strategy = Strategy.objects.create(user=user_a, name="Temporaire")
    closed(user_a, 1, 1, strategy=strategy)
    Strategy.objects.filter(pk=strategy.pk).delete()  # SET_NULL : le trade perd sa stratégie
    groups = get(client_a, "by-strategy").json()["groups"]
    assert [g["label"] for g in groups] == ["Sans stratégie"]
