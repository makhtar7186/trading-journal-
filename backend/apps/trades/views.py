from rest_framework import viewsets

from .filters import TradeFilter
from .models import Trade
from .serializers import TradeSerializer


class TradeViewSet(viewsets.ModelViewSet):
    """Trades de l'utilisateur connecté.

    Le statut est dérivé de `realized_rr` côté serveur. Envoyer `realized_rr: null`
    rouvre le trade (OPEN, `closed_at` effacé).
    """

    serializer_class = TradeSerializer
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]
    filterset_class = TradeFilter
    search_fields = ["name", "asset"]
    ordering_fields = ["trade_date", "closed_at", "created_at", "realized_rr", "asset", "name"]
    ordering = ["-trade_date", "-created_at"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):  # génération du schéma OpenAPI
            return Trade.objects.none()
        return Trade.objects.filter(user=self.request.user).select_related("strategy")
