import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q


class MarketType(models.TextChoices):
    FOREX = "FOREX", "Forex"
    METALS = "METALS", "Métaux"
    INDICES = "INDICES", "Indices"
    CRYPTO = "CRYPTO", "Crypto"


class Direction(models.TextChoices):
    BUY = "BUY", "Achat"
    SELL = "SELL", "Vente"


class Status(models.TextChoices):
    OPEN = "OPEN", "Ouvert"
    WIN = "WIN", "Gagnant"
    LOSS = "LOSS", "Perdant"
    BE = "BE", "Break-even"


class Trade(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="trades"
    )
    # SET_NULL par sécurité : une stratégie n'est normalement jamais supprimée (désactivation).
    strategy = models.ForeignKey(
        "strategies.Strategy",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="trades",
    )
    name = models.CharField(max_length=200)
    trade_date = models.DateTimeField()
    market_type = models.CharField(max_length=10, choices=MarketType.choices)
    asset = models.CharField(max_length=32)
    direction = models.CharField(max_length=4, choices=Direction.choices)
    # Dérivé de realized_rr côté serveur ; jamais saisi par le client.
    status = models.CharField(max_length=4, choices=Status.choices, default=Status.OPEN)
    planned_rr = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)
    realized_rr = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)
    entry_price = models.DecimalField(max_digits=20, decimal_places=8, null=True, blank=True)
    stop_loss = models.DecimalField(max_digits=20, decimal_places=8, null=True, blank=True)
    take_profit = models.DecimalField(max_digits=20, decimal_places=8, null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-trade_date", "-created_at"]
        indexes = [
            models.Index(fields=["user", "-trade_date"]),
            models.Index(fields=["user", "status"]),
            models.Index(fields=["user", "market_type"]),
            models.Index(fields=["user", "asset"]),
            models.Index(fields=["user", "closed_at"]),
        ]
        constraints = [
            models.CheckConstraint(
                name="trade_open_iff_no_realized_rr",
                condition=(
                    Q(status="OPEN", realized_rr__isnull=True, closed_at__isnull=True)
                    | (~Q(status="OPEN") & Q(realized_rr__isnull=False))
                ),
            ),
            models.CheckConstraint(
                name="trade_status_matches_realized_rr",
                condition=(
                    Q(status="OPEN")
                    | Q(status="WIN", realized_rr__gt=0)
                    | Q(status="LOSS", realized_rr__lt=0)
                    | Q(status="BE", realized_rr=0)
                ),
            ),
            models.CheckConstraint(
                name="trade_planned_rr_positive",
                condition=Q(planned_rr__isnull=True) | Q(planned_rr__gt=0),
            ),
        ]

    def __str__(self):
        return f"{self.name} ({self.asset})"
