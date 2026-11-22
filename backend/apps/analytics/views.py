from datetime import datetime

from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.trades.models import MarketType

from . import selectors, stats
from .filters import AnalyticsFilterSerializer, CalendarQuerySerializer, user_timezone
from .serializers import (
    CalendarSerializer,
    EquityCurveSerializer,
    GroupsSerializer,
    OverviewSerializer,
    PerformanceSerializer,
    PeriodsSerializer,
)

FILTER_DOC = [AnalyticsFilterSerializer]


class AnalyticsView(APIView):
    """Base : valide les filtres, charge les trades clôturés, délègue le calcul à stats.py.

    Le backend est la source de vérité des statistiques ; le frontend ne recalcule rien.
    """

    response_serializer = None

    def get(self, request):
        filter_serializer = AnalyticsFilterSerializer(data=request.query_params, context={"request": request})
        filter_serializer.is_valid(raise_exception=True)
        filters = filter_serializer.to_filters()
        tz = user_timezone(request.user)
        trades = selectors.closed_trades(request.user, filters, tz)
        payload = self.build(request, trades, filters, tz)
        return Response(self.response_serializer(payload).data)

    def build(self, request, trades, filters, tz) -> dict:
        raise NotImplementedError


def _ref(trade):
    if trade is None:
        return None
    return {
        "trade_id": trade.id,
        "name": trade.name,
        "asset": trade.asset,
        "closed_at": trade.closed_at,
        "realized_rr": stats.q(trade.rr),
    }


class OverviewView(AnalyticsView):
    response_serializer = OverviewSerializer

    @extend_schema(parameters=FILTER_DOC, responses=OverviewSerializer)
    def get(self, request):
        return super().get(request)

    def build(self, request, trades, filters, tz):
        summary = stats.summary(trades)
        return {
            "closed_trades": summary["trades"],
            "wins": summary["wins"],
            "losses": summary["losses"],
            "break_even": summary["break_even"],
            "open_trades": selectors.open_trades_count(request.user, filters),
            "win_rate": summary["win_rate"],
            "average_realized_rr": summary["expectancy_r"],
            "expectancy_r": summary["expectancy_r"],
            "profit_factor": summary["profit_factor"],
            "total_r": summary["total_r"],
        }


class PerformanceView(AnalyticsView):
    response_serializer = PerformanceSerializer

    @extend_schema(parameters=FILTER_DOC, responses=PerformanceSerializer)
    def get(self, request):
        return super().get(request)

    def build(self, request, trades, filters, tz):
        series = stats.streaks(trades)
        return {
            "gross_profit_r": stats.gross_profit(trades),
            "gross_loss_r": stats.gross_loss(trades),
            "average_win_r": stats.average_win(trades),
            "average_loss_r": stats.average_loss(trades),
            "best_trade": _ref(stats.best_trade(trades)),
            "worst_trade": _ref(stats.worst_trade(trades)),
            "streaks": {
                "max_win": series.max_win,
                "max_loss": series.max_loss,
                "current_type": series.current_type,
                "current_length": series.current_length,
            },
        }


class EquityCurveView(AnalyticsView):
    response_serializer = EquityCurveSerializer

    @extend_schema(parameters=FILTER_DOC, responses=EquityCurveSerializer)
    def get(self, request):
        return super().get(request)

    def build(self, request, trades, filters, tz):
        return {"trades": len(trades), "total_r": stats.total_r(trades), "points": stats.equity_curve(trades)}


class ByAssetView(AnalyticsView):
    response_serializer = GroupsSerializer

    @extend_schema(parameters=FILTER_DOC, responses=GroupsSerializer)
    def get(self, request):
        return super().get(request)

    def build(self, request, trades, filters, tz):
        groups = stats.group_by(trades, key=lambda t: t.asset)
        return {"groups": [{**g, "label": g["key"]} for g in groups]}


class ByMarketView(AnalyticsView):
    response_serializer = GroupsSerializer

    @extend_schema(parameters=FILTER_DOC, responses=GroupsSerializer)
    def get(self, request):
        return super().get(request)

    def build(self, request, trades, filters, tz):
        groups = stats.group_by(trades, key=lambda t: t.market_type)
        return {"groups": [{**g, "label": MarketType(g["key"]).label} for g in groups]}


class ByStrategyView(AnalyticsView):
    response_serializer = GroupsSerializer

    @extend_schema(parameters=FILTER_DOC, responses=GroupsSerializer)
    def get(self, request):
        return super().get(request)

    def build(self, request, trades, filters, tz):
        names = selectors.strategy_names(request.user)
        groups = stats.group_by(trades, key=lambda t: str(t.strategy_id) if t.strategy_id else None)
        return {
            "groups": [{**g, "label": names.get(g["key"], "Stratégie supprimée") if g["key"] else "Sans stratégie"} for g in groups]
        }


class CalendarView(APIView):
    """Calendrier d'un mois. Un trade clôturé figure à sa date de clôture (avec son résultat), un trade
    ouvert à sa date de prise (sans résultat). Jours calculés dans le fuseau de l'utilisateur."""

    @extend_schema(parameters=[CalendarQuerySerializer], responses=CalendarSerializer)
    def get(self, request):
        query = CalendarQuerySerializer(data=request.query_params, context={"request": request})
        query.is_valid(raise_exception=True)
        tz = user_timezone(request.user)
        month = query.validated_data.get("month") or datetime.now(tz).strftime("%Y-%m")
        year, month_number = (int(part) for part in month.split("-"))

        entries = selectors.calendar_entries(request.user, query.to_filters(), tz, year, month_number)
        days = stats.calendar_days(entries, tz)
        payload = {"month": month, "summary": stats.calendar_month_summary(days), "days": days}
        return Response(CalendarSerializer(payload).data)


class GranularitySerializer(serializers.Serializer):
    granularity = serializers.ChoiceField(choices=["day", "week", "month"], required=False, default="month")


class ByPeriodView(AnalyticsView):
    response_serializer = PeriodsSerializer

    @extend_schema(
        parameters=FILTER_DOC
        + [OpenApiParameter("granularity", str, enum=["day", "week", "month"], description="Défaut : month.")],
        responses=PeriodsSerializer,
    )
    def get(self, request):
        granularity = GranularitySerializer(data=request.query_params)
        granularity.is_valid(raise_exception=True)
        self._granularity = granularity.validated_data["granularity"]
        return super().get(request)

    def build(self, request, trades, filters, tz):
        periods = stats.by_period(trades, self._granularity, tz)
        fmt = "%Y-%m" if self._granularity == "month" else "%Y-%m-%d"
        return {
            "granularity": self._granularity,
            "periods": [{**p, "period": p["start"].strftime(fmt)} for p in periods],
        }
