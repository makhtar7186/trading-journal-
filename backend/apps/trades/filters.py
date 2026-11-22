import django_filters

from .models import Direction, MarketType, Status, Trade


class TradeFilter(django_filters.FilterSet):
    market_type = django_filters.ChoiceFilter(choices=MarketType.choices)
    direction = django_filters.ChoiceFilter(choices=Direction.choices)
    status = django_filters.ChoiceFilter(choices=Status.choices)
    asset = django_filters.CharFilter(field_name="asset", lookup_expr="iexact")
    date_from = django_filters.DateFilter(field_name="trade_date__date", lookup_expr="gte")
    date_to = django_filters.DateFilter(field_name="trade_date__date", lookup_expr="lte")

    class Meta:
        model = Trade
        fields = ["market_type", "direction", "status", "asset", "strategy", "date_from", "date_to"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Le filtre par stratégie ne propose que celles de l'utilisateur.
        request = kwargs.get("request")
        if request is not None and request.user.is_authenticated:
            self.filters["strategy"].queryset = request.user.strategies.all()
