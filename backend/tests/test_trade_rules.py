from decimal import Decimal

import pytest
from django.db import IntegrityError, transaction

from apps.trades.models import Status, Trade
from apps.trades.services import derive_status


@pytest.mark.parametrize(
    ("rr", "expected"),
    [
        (None, Status.OPEN),
        (Decimal("2.5"), Status.WIN),
        (Decimal("0.0001"), Status.WIN),
        (Decimal("-1"), Status.LOSS),
        (Decimal("-0.0001"), Status.LOSS),
        (Decimal("0"), Status.BE),
        (Decimal("0.0000"), Status.BE),
    ],
)
def test_derive_status(rr, expected):
    assert derive_status(rr) == expected


def make(user, **kwargs):
    base = dict(
        user=user,
        name="t",
        trade_date="2026-11-10T09:30:00Z",
        market_type="FOREX",
        asset="EURUSD",
        direction="BUY",
    )
    base.update(kwargs)
    return Trade(**base)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "kwargs",
    [
        {"status": "OPEN", "realized_rr": Decimal("1")},  # OPEN avec RR
        {"status": "WIN"},  # clôturé sans RR
        {"status": "WIN", "realized_rr": Decimal("-1")},  # statut incohérent
        {"status": "LOSS", "realized_rr": Decimal("1")},
        {"status": "BE", "realized_rr": Decimal("0.5")},
        {"status": "OPEN", "closed_at": "2026-11-10T10:00:00Z"},  # OPEN avec closed_at
        {"planned_rr": Decimal("0")},  # RR prévu non strictement positif
        {"planned_rr": Decimal("-1")},
    ],
)
def test_database_rejects_inconsistent_rows(user_a, kwargs):
    with pytest.raises(IntegrityError), transaction.atomic():
        make(user_a, **kwargs).save()


@pytest.mark.django_db
def test_database_accepts_consistent_rows(user_a):
    make(user_a, status="OPEN").save()
    make(user_a, status="WIN", realized_rr=Decimal("3")).save()
    make(user_a, status="LOSS", realized_rr=Decimal("-1")).save()
    make(user_a, status="BE", realized_rr=Decimal("0")).save()
    assert Trade.objects.count() == 4
