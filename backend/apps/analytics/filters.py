import re
import uuid
from dataclasses import dataclass
from datetime import date
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from rest_framework import serializers

from apps.trades.models import MarketType

NO_STRATEGY = "none"


@dataclass(frozen=True)
class Filters:
    date_from: date | None = None
    date_to: date | None = None
    market_type: str | None = None
    asset: str | None = None
    strategy: str | None = None  # None = toutes, "none" = sans stratégie, sinon UUID (str)


class AnalyticsFilterSerializer(serializers.Serializer):
    """Paramètres de requête communs à tous les endpoints analytics.

    Les dates s'appliquent à la **date de clôture** (jours calculés dans le fuseau de l'utilisateur).
    """

    date_from = serializers.DateField(required=False, help_text="Clôturés à partir de ce jour (inclus).")
    date_to = serializers.DateField(required=False, help_text="Clôturés jusqu'à ce jour (inclus).")
    market_type = serializers.ChoiceField(choices=MarketType.choices, required=False)
    asset = serializers.CharField(required=False, max_length=32)
    strategy = serializers.CharField(
        required=False, help_text="UUID d'une de vos stratégies, ou « none » pour les trades sans stratégie."
    )

    def validate_strategy(self, value):
        if value == NO_STRATEGY:
            return value
        try:
            strategy_id = uuid.UUID(value)
        except ValueError:
            raise serializers.ValidationError("Identifiant de stratégie invalide.") from None
        user = self.context["request"].user
        if not user.strategies.filter(pk=strategy_id).exists():
            raise serializers.ValidationError("Stratégie inconnue.")
        return str(strategy_id)

    def validate(self, attrs):
        start, end = attrs.get("date_from"), attrs.get("date_to")
        if start and end and start > end:
            raise serializers.ValidationError({"date_to": "La date de fin précède la date de début."})
        return attrs

    def to_filters(self) -> Filters:
        data = self.validated_data
        return Filters(
            date_from=data.get("date_from"),
            date_to=data.get("date_to"),
            market_type=data.get("market_type"),
            asset=(data["asset"].strip().upper() if data.get("asset") else None),
            strategy=data.get("strategy"),
        )


MONTH_RE = re.compile(r"^(\d{4})-(0[1-9]|1[0-2])$")


class CalendarQuerySerializer(AnalyticsFilterSerializer):
    """Mois affiché (YYYY-MM, défaut : mois courant de l'utilisateur) + filtres marché / actif / stratégie."""

    date_from = None  # la période est définie par le mois
    date_to = None
    month = serializers.CharField(required=False, help_text="YYYY-MM ; défaut : mois courant (fuseau de l'utilisateur).")

    def validate_month(self, value):
        match = MONTH_RE.match(value)
        if not match or not 2000 <= int(match.group(1)) <= 2100:
            raise serializers.ValidationError("Mois invalide (format AAAA-MM, entre 2000 et 2100).")
        return value


def user_timezone(user) -> ZoneInfo:
    try:
        return ZoneInfo(user.timezone)
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo("UTC")
