"""Formes des réponses (documentation OpenAPI + formatage des décimaux en chaînes)."""
from rest_framework import serializers


def rr_field(**kwargs):
    return serializers.DecimalField(max_digits=16, decimal_places=4, allow_null=True, **kwargs)


def percent_field(**kwargs):
    return serializers.DecimalField(max_digits=7, decimal_places=2, allow_null=True, **kwargs)


class OverviewSerializer(serializers.Serializer):
    closed_trades = serializers.IntegerField()
    wins = serializers.IntegerField()
    losses = serializers.IntegerField()
    break_even = serializers.IntegerField()
    open_trades = serializers.IntegerField(
        help_text="Trades ouverts (filtres marché/actif/stratégie ; la période ne s'applique pas)."
    )
    win_rate = percent_field(help_text="Wins / (Wins + Losses) × 100, BE exclus. null si aucun WIN ni LOSS.")
    average_realized_rr = rr_field(help_text="Σ RR réalisés / trades clôturés (BE = 0). Identique à expectancy_r.")
    expectancy_r = rr_field(help_text="Espérance en R : par définition égale à average_realized_rr. null si aucun trade clôturé.")
    profit_factor = rr_field(help_text="Σ gains / |Σ pertes|. null s'il n'y a aucune perte (jamais « infini »).")
    total_r = rr_field(help_text="Performance cumulée en R. null si aucun trade clôturé.")


class TradeRefSerializer(serializers.Serializer):
    trade_id = serializers.UUIDField()
    name = serializers.CharField()
    asset = serializers.CharField()
    closed_at = serializers.DateTimeField()
    realized_rr = rr_field()


class StreaksSerializer(serializers.Serializer):
    max_win = serializers.IntegerField(help_text="Plus longue série de gains (BE ignorés).")
    max_loss = serializers.IntegerField(help_text="Plus longue série de pertes (BE ignorés).")
    current_type = serializers.ChoiceField(choices=["WIN", "LOSS"], allow_null=True)
    current_length = serializers.IntegerField()


class PerformanceSerializer(serializers.Serializer):
    gross_profit_r = rr_field(help_text="Σ des RR positifs. null s'il n'y a aucun gain.")
    gross_loss_r = rr_field(help_text="Σ des RR négatifs (valeur négative). null s'il n'y a aucune perte.")
    average_win_r = rr_field(help_text="Gain moyen : Σ RR positifs / nombre de WIN.")
    average_loss_r = rr_field(help_text="Perte moyenne SIGNÉE (négative) : Σ RR négatifs / nombre de LOSS.")
    best_trade = TradeRefSerializer(allow_null=True, help_text="Plus gros gain ; null s'il n'y a aucun gain.")
    worst_trade = TradeRefSerializer(allow_null=True, help_text="Plus grosse perte ; null s'il n'y a aucune perte.")
    streaks = StreaksSerializer()


class EquityPointSerializer(serializers.Serializer):
    index = serializers.IntegerField()
    trade_id = serializers.UUIDField()
    name = serializers.CharField()
    asset = serializers.CharField()
    closed_at = serializers.DateTimeField()
    realized_rr = rr_field()
    cumulative_r = rr_field()


class EquityCurveSerializer(serializers.Serializer):
    trades = serializers.IntegerField()
    total_r = rr_field()
    points = EquityPointSerializer(many=True)


class SummarySerializer(serializers.Serializer):
    trades = serializers.IntegerField(help_text="Trades clôturés du groupe.")
    wins = serializers.IntegerField()
    losses = serializers.IntegerField()
    break_even = serializers.IntegerField()
    win_rate = percent_field()
    total_r = rr_field()
    expectancy_r = rr_field()
    profit_factor = rr_field()


class GroupSerializer(SummarySerializer):
    key = serializers.CharField(allow_null=True, help_text="Valeur du regroupement (null = sans stratégie).")
    label = serializers.CharField()


class GroupsSerializer(serializers.Serializer):
    groups = GroupSerializer(many=True)


class CalendarTradeSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()
    asset = serializers.CharField()
    market_type = serializers.CharField()
    direction = serializers.CharField()
    status = serializers.CharField()
    realized_rr = rr_field(source="rr", help_text="null tant que le trade est ouvert.")
    at = serializers.DateTimeField(source="when", help_text="Date de clôture (clôturé) ou de prise (ouvert).")


class CalendarDaySerializer(serializers.Serializer):
    date = serializers.DateField(help_text="Jour dans le fuseau de l'utilisateur.")
    closed_trades = serializers.IntegerField()
    wins = serializers.IntegerField()
    losses = serializers.IntegerField()
    break_even = serializers.IntegerField()
    open_trades = serializers.IntegerField(help_text="Trades encore ouverts, pris ce jour-là.")
    total_r = rr_field(help_text="Σ RR des trades clôturés ce jour-là ; null s'il n'y en a aucun (pas « 0 R »).")
    trades = CalendarTradeSerializer(many=True)


class CalendarMonthSummarySerializer(serializers.Serializer):
    closed_trades = serializers.IntegerField()
    wins = serializers.IntegerField()
    losses = serializers.IntegerField()
    break_even = serializers.IntegerField()
    open_trades = serializers.IntegerField()
    days_with_trades = serializers.IntegerField()
    total_r = rr_field()


class CalendarSerializer(serializers.Serializer):
    month = serializers.CharField()
    summary = CalendarMonthSummarySerializer()
    days = CalendarDaySerializer(many=True, help_text="Seuls les jours comportant au moins un trade, par ordre croissant.")


class PeriodSerializer(SummarySerializer):
    period = serializers.CharField(help_text="2026-11 (mois) ou 2026-11-09 (jour ; lundi pour une semaine).")
    start = serializers.DateField()


class PeriodsSerializer(serializers.Serializer):
    granularity = serializers.ChoiceField(choices=["day", "week", "month"])
    periods = PeriodSerializer(many=True)
