from rest_framework import serializers

from apps.strategies.models import Strategy

from . import services
from .models import Trade


class OwnedStrategyField(serializers.PrimaryKeyRelatedField):
    """N'accepte que les stratégies de l'utilisateur connecté (sinon « inexistante »)."""

    def get_queryset(self):
        request = self.context.get("request")
        if request is None or not request.user.is_authenticated:
            return Strategy.objects.none()
        return Strategy.objects.filter(user=request.user)


class TradeSerializer(serializers.ModelSerializer):
    strategy = OwnedStrategyField(required=False, allow_null=True)

    class Meta:
        model = Trade
        fields = [
            "id",
            "name",
            "trade_date",
            "market_type",
            "asset",
            "direction",
            "status",
            "planned_rr",
            "realized_rr",
            "strategy",
            "entry_price",
            "stop_loss",
            "take_profit",
            "notes",
            "created_at",
            "updated_at",
            "closed_at",
        ]
        # status est dérivé côté serveur ; user n'est jamais exposé en écriture.
        read_only_fields = ["id", "status", "created_at", "updated_at"]
        extra_kwargs = {"realized_rr": {"required": False, "allow_null": True}}

    def validate_name(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Le nom est obligatoire.")
        return value

    def validate_asset(self, value):
        value = value.strip().upper()
        if not value:
            raise serializers.ValidationError("L'actif est obligatoire.")
        return value

    def validate_planned_rr(self, value):
        if value is not None and value <= 0:
            raise serializers.ValidationError("Le RR prévu doit être strictement positif.")
        return value

    def validate(self, attrs):
        current_rr = self.instance.realized_rr if self.instance else None
        effective_rr = attrs.get("realized_rr", current_rr)
        if attrs.get("closed_at") is not None and effective_rr is None:
            raise serializers.ValidationError(
                {"closed_at": "Impossible de fixer une date de clôture sur un trade ouvert."}
            )
        return attrs

    def create(self, validated_data):
        return services.create_trade(user=self.context["request"].user, data=validated_data)

    def update(self, instance, validated_data):
        return services.update_trade(trade=instance, data=validated_data)
