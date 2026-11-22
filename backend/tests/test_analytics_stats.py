"""Calculs purs. Valeurs attendues calculées À LA MAIN (voir le commentaire du jeu de données A)."""
import itertools
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from apps.analytics import stats
from apps.analytics.stats import ClosedTrade

D = Decimal
BASE = datetime(2026, 11, 2, 12, 0, tzinfo=UTC)


def trade(n, rr, *, closed_at=None, created_at=None, asset="EURUSD", market="FOREX", strategy=None):
    closed_at = closed_at or BASE + timedelta(hours=n)
    return ClosedTrade(
        id=uuid.UUID(int=n),
        name=f"t{n}",
        asset=asset,
        market_type=market,
        strategy_id=strategy,
        rr=D(str(rr)),
        closed_at=closed_at,
        created_at=created_at or closed_at - timedelta(hours=1),
    )


def series(*rrs):
    return [trade(i, rr) for i, rr in enumerate(rrs, start=1)]


# Jeu de données A, dans l'ordre chronologique :  +2, +3, 0, +1, −1, −1, +1,5, −1
#   WIN  : 2 + 3 + 1 + 1,5 = 7,5  (4 trades)      LOSS : −1 −1 −1 = −3  (3 trades)      BE : 1
#   total          = 7,5 − 3 = 4,5 R              expectancy = 4,5 / 8 = 0,5625
#   win rate       = 4 / (4 + 3) × 100 = 57,142857… → 57,14   (le BE est exclu)
#   gain moyen     = 7,5 / 4 = 1,875              perte moyenne = −3 / 3 = −1
#   profit factor  = 7,5 / 3 = 2,5
#   séries (BE ignoré) : G G (BE) G → 3 gains ; P P → 2 pertes ; G ; P  → série courante = 1 perte
#   cumul          : 2, 5, 5, 6, 5, 4, 5,5, 4,5
A = series(2, 3, 0, 1, -1, -1, 1.5, -1)


class TestDatasetA:
    def test_counts_and_totals(self):
        s = stats.summary(A)
        assert (s["trades"], s["wins"], s["losses"], s["break_even"]) == (8, 4, 3, 1)
        assert s["total_r"] == D("4.5000")

    def test_win_rate_excludes_break_even(self):
        assert stats.win_rate(A) == D("57.14")

    def test_expectancy_counts_break_even_as_zero(self):
        assert stats.expectancy(A) == D("0.5625")

    def test_average_win_and_loss(self):
        assert stats.average_win(A) == D("1.8750")
        assert stats.average_loss(A) == D("-1.0000")  # signée
        assert stats.gross_profit(A) == D("7.5000")
        assert stats.gross_loss(A) == D("-3.0000")

    def test_profit_factor(self):
        assert stats.profit_factor(A) == D("2.5000")

    def test_streaks_ignore_break_even(self):
        s = stats.streaks(A)
        assert (s.max_win, s.max_loss) == (3, 2)  # le BE ne coupe pas la série 2, 3, 1
        assert (s.current_type, s.current_length) == ("LOSS", 1)

    def test_best_and_worst(self):
        assert stats.best_trade(A).id == uuid.UUID(int=2)  # +3
        assert stats.worst_trade(A).id == uuid.UUID(int=5)  # premier −1 rencontré
        assert stats.best_trade(A).rr == D("3")

    def test_equity_curve(self):
        points = stats.equity_curve(A)
        assert [p["cumulative_r"] for p in points] == [D(x) for x in ("2", "5", "5", "6", "5", "4", "5.5", "4.5")]
        assert [p["index"] for p in points] == list(range(1, 9))
        assert points[-1]["cumulative_r"] == stats.total_r(A)


class TestUndefinedStatistics:
    """Données absentes ou dénominateur nul : None (« non défini »), jamais 0 ni infini."""

    def test_no_trades(self):
        assert stats.win_rate([]) is None
        assert stats.expectancy([]) is None
        assert stats.total_r([]) is None
        assert stats.profit_factor([]) is None
        assert stats.average_win([]) is None and stats.average_loss([]) is None
        assert stats.best_trade([]) is None and stats.worst_trade([]) is None
        assert stats.equity_curve([]) == []
        s = stats.streaks([])
        assert (s.max_win, s.max_loss, s.current_type, s.current_length) == (0, 0, None, 0)
        assert stats.summary([])["trades"] == 0

    def test_only_break_even(self):
        trades = series(0, 0, 0)
        assert stats.win_rate(trades) is None  # W + L = 0
        assert stats.expectancy(trades) == D("0.0000")  # définie : 3 trades à 0 R
        assert stats.total_r(trades) == D("0.0000")
        assert stats.profit_factor(trades) is None
        assert stats.average_win(trades) is None and stats.average_loss(trades) is None
        assert stats.best_trade(trades) is None and stats.worst_trade(trades) is None
        assert stats.streaks(trades).current_type is None

    def test_only_wins_has_no_profit_factor(self):
        trades = series(1, 2)
        assert stats.profit_factor(trades) is None  # aucune perte : non défini, pas « infini »
        assert stats.win_rate(trades) == D("100.00")
        assert stats.average_loss(trades) is None
        assert stats.worst_trade(trades) is None

    def test_only_losses(self):
        trades = series(-1, -2)
        assert stats.profit_factor(trades) == D("0.0000")  # des pertes, aucun gain : défini et nul
        assert stats.win_rate(trades) == D("0.00")
        assert stats.average_win(trades) is None
        assert stats.best_trade(trades) is None  # pas de « meilleur » trade quand tout est perdant

    def test_single_trade(self):
        assert stats.win_rate(series(2)) == D("100.00")
        assert stats.expectancy(series(-1)) == D("-1.0000")


class TestPrecision:
    def test_decimal_arithmetic_has_no_float_error(self):
        trades = series("0.1", "0.1", "0.1")
        assert stats.total_r(trades) == D("0.3000")  # en float : 0.30000000000000004
        assert stats.expectancy(trades) == D("0.1000")

    @pytest.mark.parametrize(
        ("rrs", "expected"),
        [((1, 0, 0), "0.3333"), ((1, 1, 0), "0.6667"), ((1, 0, 0, 0, 0, 0, 0), "0.1429")],
    )
    def test_expectancy_rounding(self, rrs, expected):
        assert stats.expectancy(series(*rrs)) == D(expected)

    def test_win_rate_rounding_half_up(self):
        assert stats.win_rate(series(1, -1, -1)) == D("33.33")
        assert stats.win_rate(series(1, 1, -1)) == D("66.67")
        assert stats.win_rate(series(1, -1, -1, -1, -1, -1, -1, -1)) == D("12.50")

    def test_profit_factor_rounding(self):
        assert stats.profit_factor(series(2, -3)) == D("0.6667")


class TestOrderingAndStability:
    def test_same_closed_at_uses_created_at_then_id(self):
        moment = BASE
        a = trade(3, 1, closed_at=moment, created_at=moment - timedelta(minutes=5))
        b = trade(1, 2, closed_at=moment, created_at=moment - timedelta(minutes=5))  # même created_at : id décide
        c = trade(2, 3, closed_at=moment, created_at=moment - timedelta(minutes=9))  # créé plus tôt
        ordered = stats.chronological([a, b, c])
        assert [t.id.int for t in ordered] == [2, 1, 3]

    def test_every_permutation_gives_the_same_curve_and_streaks(self):
        moment = BASE
        trades = [
            trade(1, 2, closed_at=moment),
            trade(2, -1, closed_at=moment),
            trade(3, 3, closed_at=moment),
            trade(4, -2, closed_at=moment + timedelta(hours=1)),
        ]
        reference = stats.equity_curve(trades)
        ref_streaks = stats.streaks(trades)
        for perm in itertools.permutations(trades):
            assert stats.equity_curve(list(perm)) == reference
            assert stats.streaks(list(perm)) == ref_streaks

    def test_break_even_does_not_break_a_streak(self):
        assert stats.streaks(series(1, 0, 1)).max_win == 2
        assert stats.streaks(series(-1, 0, -1)).max_loss == 2

    def test_current_streak_is_the_last_non_be_run(self):
        s = stats.streaks(series(-1, 2, 3, 0))
        assert (s.current_type, s.current_length) == ("WIN", 2)


class TestGroupsAndPeriods:
    def test_group_by_sorts_by_total_then_key(self):
        trades = [
            trade(1, 2, asset="XAUUSD"),
            trade(2, -1, asset="EURUSD"),
            trade(3, 1, asset="XAUUSD"),
            trade(4, 3, asset="BTCUSD"),
        ]
        groups = stats.group_by(trades, key=lambda t: t.asset)
        # XAUUSD et BTCUSD valent 3 R chacun : égalité départagée par la clé (ordre alphabétique) ; EURUSD = −1 R.
        assert [g["key"] for g in groups] == ["BTCUSD", "XAUUSD", "EURUSD"]
        xau = groups[1]
        assert (xau["trades"], xau["wins"], xau["total_r"], xau["win_rate"]) == (2, 2, D("3.0000"), D("100.00"))
        assert xau["profit_factor"] is None  # aucune perte dans ce groupe

    def test_period_uses_the_user_timezone_for_day_boundaries(self):
        late = trade(1, 1, closed_at=datetime(2026, 11, 10, 23, 30, tzinfo=UTC))
        paris, utc = ZoneInfo("Europe/Paris"), ZoneInfo("UTC")
        assert stats.by_period([late], "day", paris)[0]["start"].isoformat() == "2026-11-11"
        assert stats.by_period([late], "day", utc)[0]["start"].isoformat() == "2026-11-10"

    def test_period_month_boundary_depends_on_timezone(self):
        edge = trade(1, 1, closed_at=datetime(2026, 11, 30, 23, 30, tzinfo=UTC))
        assert stats.by_period([edge], "month", ZoneInfo("Europe/Paris"))[0]["start"].isoformat() == "2026-12-01"
        assert stats.by_period([edge], "month", ZoneInfo("UTC"))[0]["start"].isoformat() == "2026-11-01"

    @pytest.mark.parametrize(
        ("closed", "week_start"),
        [
            ((2026, 11, 9), "2026-11-09"),  # lundi
            ((2026, 11, 11), "2026-11-09"),  # mercredi
            ((2026, 11, 15), "2026-11-09"),  # dimanche
            ((2026, 11, 16), "2026-11-16"),  # lundi suivant
        ],
    )
    def test_week_starts_on_monday(self, closed, week_start):
        t = trade(1, 1, closed_at=datetime(*closed, 12, 0, tzinfo=UTC))
        assert stats.by_period([t], "week", ZoneInfo("UTC"))[0]["start"].isoformat() == week_start

    def test_periods_are_sorted_and_aggregated(self):
        trades = [
            trade(1, 2, closed_at=datetime(2026, 12, 3, 10, tzinfo=UTC)),
            trade(2, -1, closed_at=datetime(2026, 11, 3, 10, tzinfo=UTC)),
            trade(3, 1, closed_at=datetime(2026, 11, 20, 10, tzinfo=UTC)),
        ]
        periods = stats.by_period(trades, "month", ZoneInfo("UTC"))
        assert [p["start"].isoformat() for p in periods] == ["2026-11-01", "2026-12-01"]
        assert (periods[0]["trades"], periods[0]["total_r"]) == (2, D("0.0000"))
        assert periods[1]["total_r"] == D("2.0000")
