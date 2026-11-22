"""Calculs statistiques. Fonctions pures sur des Decimal : aucune dépendance HTTP ni base.

Règles (dossier de conception §4.3) :
- seules les opérations clôturées (WIN, LOSS, BE) entrent dans les calculs ;
- un indicateur dont les données requises sont absentes vaut None (« non défini »), jamais 0 ni l'infini ;
- ordre chronologique stable : (closed_at, created_at, id).
"""
import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from zoneinfo import ZoneInfo

ZERO = Decimal("0")
Q2 = Decimal("0.01")
Q4 = Decimal("0.0001")


@dataclass(frozen=True)
class ClosedTrade:
    id: uuid.UUID
    name: str
    asset: str
    market_type: str
    strategy_id: uuid.UUID | None
    rr: Decimal  # RR réalisé
    closed_at: datetime
    created_at: datetime


def q(value: Decimal, quantum: Decimal = Q4) -> Decimal:
    return value.quantize(quantum, rounding=ROUND_HALF_UP)


def chronological(trades: list[ClosedTrade]) -> list[ClosedTrade]:
    """Ordre stable, y compris quand plusieurs trades partagent la même date de clôture."""
    return sorted(trades, key=lambda t: (t.closed_at, t.created_at, t.id))


def _wins(trades):
    return [t for t in trades if t.rr > ZERO]


def _losses(trades):
    return [t for t in trades if t.rr < ZERO]


def _be(trades):
    return [t for t in trades if t.rr == ZERO]


def total_r(trades: list[ClosedTrade]) -> Decimal | None:
    return q(sum((t.rr for t in trades), ZERO)) if trades else None


def win_rate(trades: list[ClosedTrade]) -> Decimal | None:
    """Wins / (Wins + Losses) × 100 ; les BE sont exclus du dénominateur."""
    wins, losses = len(_wins(trades)), len(_losses(trades))
    if wins + losses == 0:
        return None
    return q(Decimal(wins) / Decimal(wins + losses) * 100, Q2)


def expectancy(trades: list[ClosedTrade]) -> Decimal | None:
    """Moyenne des RR réalisés de tous les trades clôturés (les BE comptent pour 0)."""
    if not trades:
        return None
    return q(sum((t.rr for t in trades), ZERO) / len(trades))


def average_win(trades: list[ClosedTrade]) -> Decimal | None:
    wins = _wins(trades)
    return q(sum((t.rr for t in wins), ZERO) / len(wins)) if wins else None


def average_loss(trades: list[ClosedTrade]) -> Decimal | None:
    """Perte moyenne, SIGNÉE (négative) : −1 signifie une perte moyenne de 1R."""
    losses = _losses(trades)
    return q(sum((t.rr for t in losses), ZERO) / len(losses)) if losses else None


def gross_profit(trades: list[ClosedTrade]) -> Decimal | None:
    wins = _wins(trades)
    return q(sum((t.rr for t in wins), ZERO)) if wins else None


def gross_loss(trades: list[ClosedTrade]) -> Decimal | None:
    losses = _losses(trades)
    return q(sum((t.rr for t in losses), ZERO)) if losses else None


def profit_factor(trades: list[ClosedTrade]) -> Decimal | None:
    """Σ gains / |Σ pertes|. Non défini (None) s'il n'y a aucune perte — jamais « infini »."""
    losses = _losses(trades)
    if not losses:
        return None
    gains = sum((t.rr for t in _wins(trades)), ZERO)
    return q(gains / abs(sum((t.rr for t in losses), ZERO)))


def best_trade(trades: list[ClosedTrade]) -> ClosedTrade | None:
    """Meilleure opération : seulement s'il existe au moins un gain (sinon « meilleure » serait trompeur)."""
    wins = chronological(_wins(trades))
    return max(wins, key=lambda t: t.rr) if wins else None


def worst_trade(trades: list[ClosedTrade]) -> ClosedTrade | None:
    losses = chronological(_losses(trades))
    return min(losses, key=lambda t: t.rr) if losses else None


@dataclass(frozen=True)
class Streaks:
    max_win: int
    max_loss: int
    current_type: str | None  # "WIN" | "LOSS" | None
    current_length: int


def streaks(trades: list[ClosedTrade]) -> Streaks:
    """Séries de gains / pertes consécutifs. Les BE sont IGNORÉS (ni rupture, ni prolongation)."""
    max_win = max_loss = run = 0
    run_type: str | None = None
    for trade in chronological(trades):
        if trade.rr == ZERO:
            continue
        kind = "WIN" if trade.rr > ZERO else "LOSS"
        run = run + 1 if kind == run_type else 1
        run_type = kind
        if kind == "WIN":
            max_win = max(max_win, run)
        else:
            max_loss = max(max_loss, run)
    return Streaks(max_win, max_loss, run_type, run if run_type else 0)


def equity_curve(trades: list[ClosedTrade]) -> list[dict]:
    """Somme cumulative des RR réalisés, triée par (closed_at, created_at, id)."""
    cumulative = ZERO
    points = []
    for index, trade in enumerate(chronological(trades), start=1):
        cumulative += trade.rr
        points.append(
            {
                "index": index,
                "trade_id": trade.id,
                "name": trade.name,
                "asset": trade.asset,
                "closed_at": trade.closed_at,
                "realized_rr": q(trade.rr),
                "cumulative_r": q(cumulative),
            }
        )
    return points


def summary(trades: list[ClosedTrade]) -> dict:
    """Indicateurs communs aux regroupements (par actif, marché, stratégie, période)."""
    return {
        "trades": len(trades),
        "wins": len(_wins(trades)),
        "losses": len(_losses(trades)),
        "break_even": len(_be(trades)),
        "win_rate": win_rate(trades),
        "total_r": total_r(trades),
        "expectancy_r": expectancy(trades),
        "profit_factor": profit_factor(trades),
    }


def group_by(trades: list[ClosedTrade], key) -> list[dict]:
    """Résultats par clé (actif, marché, stratégie…), du plus rentable au moins rentable."""
    buckets: dict = defaultdict(list)
    for trade in chronological(trades):
        buckets[key(trade)].append(trade)
    groups = [{"key": k, **summary(items)} for k, items in buckets.items()]
    groups.sort(key=lambda g: (-g["total_r"], str(g["key"])))
    return groups


@dataclass(frozen=True)
class CalendarEntry:
    """Un trade placé sur le calendrier : clôturé → à sa date de clôture ; ouvert → à sa date de prise."""

    id: uuid.UUID
    name: str
    asset: str
    market_type: str
    direction: str
    status: str
    rr: Decimal | None  # None tant que le trade est ouvert
    when: datetime  # closed_at (clôturé) ou trade_date (ouvert)
    created_at: datetime


def calendar_days(entries: list[CalendarEntry], tz: ZoneInfo) -> list[dict]:
    """Regroupe les entrées par jour LOCAL (fuseau de l'utilisateur), jours triés, trades triés dans le jour.

    `total_r` d'un jour = somme des RR des trades clôturés ce jour-là ; None s'il n'y en a aucun
    (un jour avec seulement des trades ouverts n'a pas de résultat, ce n'est pas « 0 R »).
    """
    buckets: dict[date, list[CalendarEntry]] = defaultdict(list)
    for entry in sorted(entries, key=lambda e: (e.when, e.created_at, e.id)):
        buckets[entry.when.astimezone(tz).date()].append(entry)

    days = []
    for day in sorted(buckets):
        items = buckets[day]
        closed = [e for e in items if e.rr is not None]
        rrs = [e.rr for e in closed]
        days.append(
            {
                "date": day,
                "closed_trades": len(closed),
                "wins": sum(1 for r in rrs if r > ZERO),
                "losses": sum(1 for r in rrs if r < ZERO),
                "break_even": sum(1 for r in rrs if r == ZERO),
                "open_trades": len(items) - len(closed),
                "total_r": q(sum(rrs, ZERO)) if rrs else None,
                "trades": items,
            }
        )
    return days


def calendar_month_summary(days: list[dict]) -> dict:
    """Totaux du mois, déduits des jours (donc cohérents avec la grille)."""
    closed = sum(d["closed_trades"] for d in days)
    results = [d["total_r"] for d in days if d["total_r"] is not None]
    return {
        "closed_trades": closed,
        "wins": sum(d["wins"] for d in days),
        "losses": sum(d["losses"] for d in days),
        "break_even": sum(d["break_even"] for d in days),
        "open_trades": sum(d["open_trades"] for d in days),
        "days_with_trades": len(days),
        "total_r": q(sum(results, ZERO)) if results else None,
    }


def period_start(moment: datetime, granularity: str, tz: ZoneInfo) -> date:
    local = moment.astimezone(tz).date()
    if granularity == "day":
        return local
    if granularity == "week":
        return local - timedelta(days=local.weekday())  # lundi
    return local.replace(day=1)  # month


def by_period(trades: list[ClosedTrade], granularity: str, tz: ZoneInfo) -> list[dict]:
    """Résultats par jour / semaine (lundi) / mois, calculés dans le fuseau de l'utilisateur."""
    buckets: dict[date, list[ClosedTrade]] = defaultdict(list)
    for trade in chronological(trades):
        buckets[period_start(trade.closed_at, granularity, tz)].append(trade)
    return [{"start": start, **summary(buckets[start])} for start in sorted(buckets)]
