"""Lectures : construit les données d'entrée des calculs. Les filtres sont appliqués AVANT toute agrégation."""
from datetime import datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from apps.strategies.models import Strategy
from apps.trades.models import Status, Trade

from .filters import NO_STRATEGY, Filters
from .stats import CalendarEntry, ClosedTrade


def _scoped(user, filters: Filters):
    """Trades de l'utilisateur, restreints par marché, actif et stratégie (pas par période)."""
    qs = Trade.objects.filter(user=user)
    if filters.market_type:
        qs = qs.filter(market_type=filters.market_type)
    if filters.asset:
        qs = qs.filter(asset__iexact=filters.asset)
    if filters.strategy == NO_STRATEGY:
        qs = qs.filter(strategy__isnull=True)
    elif filters.strategy:
        qs = qs.filter(strategy_id=filters.strategy)
    return qs


def closed_trades(user, filters: Filters, tz: ZoneInfo) -> list[ClosedTrade]:
    """Trades clôturés (WIN/LOSS/BE) dont la date de clôture, dans le fuseau de l'utilisateur, est dans la période.

    Les trades OPEN n'en font jamais partie.
    """
    qs = _scoped(user, filters).exclude(status=Status.OPEN).filter(realized_rr__isnull=False, closed_at__isnull=False)
    if filters.date_from:
        qs = qs.filter(closed_at__gte=datetime.combine(filters.date_from, time.min, tzinfo=tz))
    if filters.date_to:
        # Borne haute exclusive : le jour `date_to` entier est inclus.
        qs = qs.filter(closed_at__lt=datetime.combine(filters.date_to + timedelta(days=1), time.min, tzinfo=tz))
    rows = qs.values_list(
        "id", "name", "asset", "market_type", "strategy_id", "realized_rr", "closed_at", "created_at"
    )
    return [
        ClosedTrade(id=i, name=n, asset=a, market_type=m, strategy_id=s, rr=Decimal(rr), closed_at=c, created_at=cr)
        for i, n, a, m, s, rr, c, cr in rows
    ]


def open_trades_count(user, filters: Filters) -> int:
    """Trades ouverts correspondant aux filtres marché/actif/stratégie (la période ne s'applique pas : pas de clôture)."""
    return _scoped(user, filters).filter(status=Status.OPEN).count()


def calendar_entries(user, filters: Filters, tz: ZoneInfo, year: int, month: int) -> list[CalendarEntry]:
    """Trades du mois : clôturés (par date de clôture) + encore ouverts (par date de prise), dans le fuseau de l'utilisateur."""
    start = datetime(year, month, 1, tzinfo=tz)
    end = datetime(year + (month == 12), month % 12 + 1, 1, tzinfo=tz)  # borne haute exclusive
    scoped = _scoped(user, filters)
    columns = ("id", "name", "asset", "market_type", "direction", "status", "realized_rr", "created_at")

    closed = (
        scoped.exclude(status=Status.OPEN)
        .filter(realized_rr__isnull=False, closed_at__gte=start, closed_at__lt=end)
        .values_list(*columns, "closed_at")
    )
    opened = scoped.filter(status=Status.OPEN, trade_date__gte=start, trade_date__lt=end).values_list(*columns, "trade_date")

    entries = []
    for i, n, a, m, d, s, rr, cr, when in closed:
        entries.append(CalendarEntry(i, n, a, m, d, s, Decimal(rr), when, cr))
    for i, n, a, m, d, s, _rr, cr, when in opened:
        entries.append(CalendarEntry(i, n, a, m, d, s, None, when, cr))
    return entries


def strategy_names(user) -> dict[str, str]:
    return {str(pk): name for pk, name in Strategy.objects.filter(user=user).values_list("id", "name")}
