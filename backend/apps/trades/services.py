"""Règles métier des trades. Les vues et serializers n'y dérogent jamais."""
from datetime import datetime
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from .models import Status, Trade

ZERO = Decimal("0")


def derive_status(realized_rr: Decimal | None) -> str:
    """OPEN sans RR réalisé ; sinon > 0 WIN, < 0 LOSS, = 0 BE."""
    if realized_rr is None:
        return Status.OPEN
    if realized_rr > ZERO:
        return Status.WIN
    if realized_rr < ZERO:
        return Status.LOSS
    return Status.BE


def apply_realized_rr(
    trade: Trade, realized_rr: Decimal | None, closed_at: datetime | None = None
) -> None:
    """Applique un RR réalisé : statut dérivé, closed_at géré.

    realized_rr=None rouvre le trade (OPEN, closed_at effacé).
    """
    trade.realized_rr = realized_rr
    trade.status = derive_status(realized_rr)
    if realized_rr is None:
        trade.closed_at = None
    else:
        trade.closed_at = closed_at or trade.closed_at or timezone.now()


@transaction.atomic
def create_trade(*, user, data: dict) -> Trade:
    data = dict(data)
    realized_rr = data.pop("realized_rr", None)
    closed_at = data.pop("closed_at", None)
    trade = Trade(user=user, **data)
    apply_realized_rr(trade, realized_rr, closed_at)
    trade.save()
    return trade


@transaction.atomic
def update_trade(*, trade: Trade, data: dict) -> Trade:
    data = dict(data)
    has_rr = "realized_rr" in data
    realized_rr = data.pop("realized_rr", None)
    closed_at = data.pop("closed_at", None)
    for field, value in data.items():
        setattr(trade, field, value)
    if has_rr:
        apply_realized_rr(trade, realized_rr, closed_at)
    elif closed_at is not None and trade.realized_rr is not None:
        trade.closed_at = closed_at
    trade.save()
    return trade
