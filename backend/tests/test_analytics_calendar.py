import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.analytics import stats
from apps.analytics.stats import CalendarEntry
from apps.trades.models import Trade
from apps.trades.services import derive_status

D = Decimal
PARIS, UTC_TZ = ZoneInfo("Europe/Paris"), ZoneInfo("UTC")
BASE = datetime(2026, 11, 10, 12, 0, tzinfo=UTC)


def entry(n, rr, when, *, created_at=None):
    return CalendarEntry(
        id=uuid.UUID(int=n),
        name=f"t{n}",
        asset="EURUSD",
        market_type="FOREX",
        direction="BUY",
        status="OPEN" if rr is None else ("WIN" if rr > 0 else "LOSS" if rr < 0 else "BE"),
        rr=None if rr is None else D(str(rr)),
        when=when,
        created_at=created_at or when - timedelta(hours=1),
    )


# --- calculs purs ------------------------------------------------------------------


class TestCalendarDays:
    def test_empty(self):
        assert stats.calendar_days([], UTC_TZ) == []
        assert stats.calendar_month_summary([]) == {
            "closed_trades": 0, "wins": 0, "losses": 0, "break_even": 0, "open_trades": 0, "days_with_trades": 0, "total_r": None,
        }

    def test_daily_result_is_the_sum_of_that_days_closed_trades(self):
        entries = [entry(1, 2, BASE), entry(2, -1, BASE + timedelta(hours=1)), entry(3, 0, BASE + timedelta(hours=2))]
        [day] = stats.calendar_days(entries, UTC_TZ)
        assert day["date"].isoformat() == "2026-11-10"
        assert (day["closed_trades"], day["wins"], day["losses"], day["break_even"]) == (3, 1, 1, 1)
        assert day["total_r"] == D("1.0000")

    def test_day_with_only_open_trades_has_no_result_not_zero(self):
        [day] = stats.calendar_days([entry(1, None, BASE)], UTC_TZ)
        assert day["total_r"] is None
        assert (day["closed_trades"], day["open_trades"]) == (0, 1)

    def test_open_trades_do_not_change_the_daily_result(self):
        [day] = stats.calendar_days([entry(1, 2, BASE), entry(2, None, BASE + timedelta(hours=1))], UTC_TZ)
        assert day["total_r"] == D("2.0000")
        assert (day["closed_trades"], day["open_trades"], len(day["trades"])) == (1, 1, 2)

    def test_a_day_of_break_even_trades_is_zero_r_not_undefined(self):
        [day] = stats.calendar_days([entry(1, 0, BASE)], UTC_TZ)
        assert day["total_r"] == D("0.0000")

    def test_days_use_the_user_timezone(self):
        late = entry(1, 1, datetime(2026, 11, 10, 23, 30, tzinfo=UTC))
        assert stats.calendar_days([late], PARIS)[0]["date"].isoformat() == "2026-11-11"
        assert stats.calendar_days([late], UTC_TZ)[0]["date"].isoformat() == "2026-11-10"

    def test_days_sorted_and_trades_ordered_inside_a_day(self):
        entries = [
            entry(3, 1, BASE + timedelta(days=2)),
            entry(2, 1, BASE + timedelta(hours=3)),
            entry(1, 1, BASE),
        ]
        days = stats.calendar_days(entries, UTC_TZ)
        assert [d["date"].isoformat() for d in days] == ["2026-11-10", "2026-11-12"]
        assert [e.id.int for e in days[0]["trades"]] == [1, 2]

    def test_same_instant_is_ordered_by_created_at_then_id(self):
        a = entry(5, 1, BASE, created_at=BASE - timedelta(minutes=1))
        b = entry(4, 1, BASE, created_at=BASE - timedelta(minutes=1))
        c = entry(9, 1, BASE, created_at=BASE - timedelta(minutes=9))
        [day] = stats.calendar_days([a, b, c], UTC_TZ)
        assert [e.id.int for e in day["trades"]] == [9, 4, 5]

    def test_month_summary_is_consistent_with_the_days(self):
        entries = [entry(1, 2, BASE), entry(2, -1, BASE + timedelta(days=1)), entry(3, None, BASE + timedelta(days=2)), entry(4, 0, BASE + timedelta(days=2))]
        days = stats.calendar_days(entries, UTC_TZ)
        s = stats.calendar_month_summary(days)
        assert s == {"closed_trades": 3, "wins": 1, "losses": 1, "break_even": 1, "open_trades": 1, "days_with_trades": 3, "total_r": D("1.0000")}

    def test_summary_total_is_undefined_when_nothing_was_closed(self):
        s = stats.calendar_month_summary(stats.calendar_days([entry(1, None, BASE)], UTC_TZ))
        assert s["total_r"] is None and s["open_trades"] == 1


# --- API -----------------------------------------------------------------------------


def put_closed(user, rr, when, *, asset="EURUSD", market="FOREX", strategy=None, name=None):
    return Trade.objects.create(
        user=user, name=name or f"{asset} {rr}", trade_date=when - timedelta(hours=2), market_type=market, asset=asset,
        direction="BUY", status=derive_status(D(str(rr))), realized_rr=D(str(rr)), closed_at=when, strategy=strategy,
    )


def put_open(user, when, *, asset="EURUSD", market="FOREX", strategy=None, name="ouvert"):
    return Trade.objects.create(user=user, name=name, trade_date=when, market_type=market, asset=asset, direction="SELL", strategy=strategy)


def calendar(client, **params):
    return client.get("/api/v1/analytics/calendar/", params)


def days_of(response):
    return {d["date"]: d for d in response.json()["days"]}


@pytest.mark.django_db
def test_closed_trade_on_its_closing_day_and_open_trade_on_its_opening_day(client_a, user_a):
    put_closed(user_a, 2, datetime(2026, 11, 10, 15, tzinfo=UTC), name="gagnant")
    put_open(user_a, datetime(2026, 11, 12, 9, tzinfo=UTC), name="en cours")

    response = calendar(client_a, month="2026-11")
    assert response.status_code == 200
    days = days_of(response)
    assert set(days) == {"2026-11-10", "2026-11-12"}

    closed_day = days["2026-11-10"]
    assert closed_day["total_r"] == "2.0000" and closed_day["closed_trades"] == 1
    [trade] = closed_day["trades"]
    assert (trade["name"], trade["status"], trade["realized_rr"], trade["direction"]) == ("gagnant", "WIN", "2.0000", "BUY")

    open_day = days["2026-11-12"]
    assert open_day["total_r"] is None and open_day["open_trades"] == 1
    assert open_day["trades"][0]["realized_rr"] is None and open_day["trades"][0]["status"] == "OPEN"


@pytest.mark.django_db
def test_only_the_requested_month_is_returned(client_a, user_a):
    put_closed(user_a, 1, datetime(2026, 10, 31, 12, tzinfo=UTC))
    put_closed(user_a, 1, datetime(2026, 11, 1, 0, 0, tzinfo=UTC))
    put_closed(user_a, 1, datetime(2026, 11, 30, 12, tzinfo=UTC))
    put_closed(user_a, 1, datetime(2026, 12, 1, 0, 0, tzinfo=UTC))
    assert sorted(days_of(calendar(client_a, month="2026-11"))) == ["2026-11-01", "2026-11-30"]
    assert sorted(days_of(calendar(client_a, month="2026-10"))) == ["2026-10-31"]


@pytest.mark.django_db
def test_open_trades_of_other_months_are_not_shown(client_a, user_a):
    put_open(user_a, datetime(2026, 10, 5, 9, tzinfo=UTC), name="octobre")
    put_open(user_a, datetime(2026, 11, 5, 9, tzinfo=UTC), name="novembre")
    put_open(user_a, datetime(2026, 12, 5, 9, tzinfo=UTC), name="décembre")
    names = [t["name"] for d in calendar(client_a, month="2026-11").json()["days"] for t in d["trades"]]
    assert names == ["novembre"]


@pytest.mark.django_db
def test_year_rollover(client_a, user_a):
    put_closed(user_a, 1, datetime(2026, 12, 31, 12, tzinfo=UTC))
    put_closed(user_a, 1, datetime(2027, 1, 1, 12, tzinfo=UTC))
    assert sorted(days_of(calendar(client_a, month="2026-12"))) == ["2026-12-31"]
    assert sorted(days_of(calendar(client_a, month="2027-01"))) == ["2027-01-01"]


@pytest.mark.django_db
def test_month_and_day_boundaries_follow_the_user_timezone(client_a, user_a):
    put_closed(user_a, 1, datetime(2026, 11, 30, 23, 30, tzinfo=UTC))  # = 1er décembre 00:30 à Paris
    assert sorted(days_of(calendar(client_a, month="2026-11"))) == ["2026-11-30"]  # UTC

    user_a.timezone = "Europe/Paris"
    user_a.save()
    assert days_of(calendar(client_a, month="2026-11")) == {}
    assert sorted(days_of(calendar(client_a, month="2026-12"))) == ["2026-12-01"]


@pytest.mark.django_db
def test_default_month_is_the_current_month(client_a, user_a):
    put_closed(user_a, 1, timezone.now() - timedelta(minutes=5))
    response = calendar(client_a)
    assert response.status_code == 200
    assert response.json()["month"] == timezone.now().strftime("%Y-%m")
    assert response.json()["summary"]["closed_trades"] == 1


@pytest.mark.django_db
def test_reopened_trade_moves_to_its_opening_day(client_a, user_a):
    trade = put_closed(user_a, 2, datetime(2026, 11, 20, 12, tzinfo=UTC))
    Trade.objects.filter(pk=trade.pk).update(trade_date=datetime(2026, 11, 18, 9, tzinfo=UTC))  # pris le 18, clôturé le 20

    before = days_of(calendar(client_a, month="2026-11"))
    assert list(before) == ["2026-11-20"] and before["2026-11-20"]["total_r"] == "2.0000"

    client_a.patch(f"/api/v1/trades/{trade.pk}/", {"realized_rr": None}, format="json")
    after = days_of(calendar(client_a, month="2026-11"))
    assert list(after) == ["2026-11-18"]  # il revient à sa date de prise
    assert after["2026-11-18"]["total_r"] is None
    assert after["2026-11-18"]["trades"][0]["status"] == "OPEN"


@pytest.mark.django_db
def test_summary_matches_the_statistics_of_the_same_month(client_a, user_a):
    """La grille et les analytics ne doivent jamais se contredire."""
    for i, rr in enumerate([2, 3, 0, 1, -1, -1], start=1):
        put_closed(user_a, rr, datetime(2026, 11, i * 4, 12, tzinfo=UTC))
    put_closed(user_a, 5, datetime(2026, 10, 15, 12, tzinfo=UTC))  # hors mois
    put_open(user_a, datetime(2026, 11, 8, 9, tzinfo=UTC))

    summary = calendar(client_a, month="2026-11").json()["summary"]
    overview = client_a.get("/api/v1/analytics/overview/", {"date_from": "2026-11-01", "date_to": "2026-11-30"}).json()
    assert summary["total_r"] == overview["total_r"] == "4.0000"
    assert (summary["closed_trades"], summary["wins"], summary["losses"], summary["break_even"]) == (
        overview["closed_trades"], overview["wins"], overview["losses"], overview["break_even"],
    )
    assert summary["open_trades"] == 1
    # et la somme des jours = le total du mois
    days = calendar(client_a, month="2026-11").json()["days"]
    assert sum(Decimal(d["total_r"]) for d in days if d["total_r"] is not None) == Decimal(summary["total_r"])


@pytest.mark.django_db
def test_filters(client_a, user_a, strategy_a):
    put_closed(user_a, 2, datetime(2026, 11, 10, 12, tzinfo=UTC), asset="XAUUSD", market="METALS", strategy=strategy_a)
    put_closed(user_a, -1, datetime(2026, 11, 10, 13, tzinfo=UTC), asset="EURUSD", market="FOREX")
    put_open(user_a, datetime(2026, 11, 11, 9, tzinfo=UTC), asset="EURUSD", market="FOREX")

    def names(**params):
        return sorted(t["name"] for d in calendar(client_a, month="2026-11", **params).json()["days"] for t in d["trades"])

    assert len(names()) == 3
    assert names(market_type="METALS") == ["XAUUSD 2"]
    assert names(asset="eurusd") == ["EURUSD -1", "ouvert"]
    assert names(strategy=str(strategy_a.pk)) == ["XAUUSD 2"]
    assert len(names(strategy="none")) == 2
    day = days_of(calendar(client_a, month="2026-11", market_type="FOREX"))["2026-11-10"]
    assert day["total_r"] == "-1.0000"  # le total du jour respecte le filtre


@pytest.mark.django_db
@pytest.mark.parametrize("month", ["2026-13", "2026-00", "2026-1", "abcd", "1999-12", "2101-01", "2026/11", ""])
def test_invalid_month(client_a, month):
    response = calendar(client_a, month=month) if month else None
    if response is not None:
        assert response.status_code == 400
        assert "month" in response.json()


@pytest.mark.django_db
def test_invalid_filters_and_foreign_strategy(client_a, strategy_b):
    assert calendar(client_a, month="2026-11", market_type="STOCKS").status_code == 400
    assert calendar(client_a, month="2026-11", strategy=str(strategy_b.pk)).status_code == 400


@pytest.mark.django_db
def test_isolation_between_users(client_a, client_b, user_a, user_b):
    put_closed(user_b, 9, datetime(2026, 11, 10, 12, tzinfo=UTC), name="secret de bob")
    put_open(user_b, datetime(2026, 11, 11, 9, tzinfo=UTC))
    put_closed(user_a, 1, datetime(2026, 11, 10, 12, tzinfo=UTC), name="à alice")
    mine = calendar(client_a, month="2026-11").json()
    assert [t["name"] for d in mine["days"] for t in d["trades"]] == ["à alice"]
    assert mine["summary"]["total_r"] == "1.0000"
    assert len(calendar(client_b, month="2026-11").json()["days"]) == 2


@pytest.mark.django_db
def test_requires_authentication():
    assert calendar(APIClient(), month="2026-11").status_code in (401, 403)


@pytest.mark.django_db
def test_empty_month(client_a):
    data = calendar(client_a, month="2026-11").json()
    assert data["days"] == []
    assert data["summary"]["total_r"] is None and data["summary"]["days_with_trades"] == 0
