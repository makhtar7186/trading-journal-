from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status, viewsets
from rest_framework.response import Response

from .models import Strategy
from .serializers import StrategySerializer


class StrategyViewSet(viewsets.ModelViewSet):
    """Stratégies de l'utilisateur connecté.

    DELETE **désactive** la stratégie (is_active=false) au lieu de la supprimer :
    l'historique des trades reste intact. PATCH is_active=true la réactive.
    """

    serializer_class = StrategySerializer
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]
    filterset_fields = ["is_active"]
    search_fields = ["name", "description"]
    ordering_fields = ["name", "created_at", "updated_at"]
    ordering = ["name"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):  # génération du schéma OpenAPI
            return Strategy.objects.none()
        return Strategy.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @extend_schema(responses={204: OpenApiResponse(description="Stratégie désactivée")})
    def destroy(self, request, *args, **kwargs):
        strategy = self.get_object()
        if strategy.is_active:
            strategy.is_active = False
            strategy.save(update_fields=["is_active", "updated_at"])
        return Response(status=status.HTTP_204_NO_CONTENT)
