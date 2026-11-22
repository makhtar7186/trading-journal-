import re

from django.http import FileResponse, Http404, HttpResponseRedirect
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import generics, status
from rest_framework.exceptions import ValidationError
from rest_framework.generics import get_object_or_404
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.trades.models import Trade
from core.storage import FileNotFoundInStorage, StorageError, get_storage

from .images import CONTENT_TYPE_BY_EXT
from .models import ScreenshotCategory, TradeScreenshot
from .serializers import ScreenshotSerializer, ScreenshotUploadSerializer
from .services import UploadRejected, create_screenshots

SIGNED_URL_TTL_SECONDS = 60


class TradeScreenshotListCreateView(APIView):
    """Captures d'un trade de l'utilisateur connecté (liste non paginée, tri chronologique)."""

    parser_classes = [MultiPartParser, FormParser]

    def _trade(self, request, trade_id):
        # Un trade d'autrui est indiscernable d'un trade inexistant : 404.
        return get_object_or_404(Trade.objects.filter(user=request.user), pk=trade_id)

    @extend_schema(
        responses={200: ScreenshotSerializer(many=True)},
        parameters=[],
    )
    def get(self, request, trade_id):
        trade = self._trade(request, trade_id)
        queryset = trade.screenshots.all()
        category = request.query_params.get("category")
        if category in ScreenshotCategory.values:
            queryset = queryset.filter(category=category)
        return Response(ScreenshotSerializer(queryset, many=True).data)

    @extend_schema(
        request={"multipart/form-data": ScreenshotUploadSerializer},
        responses={
            201: ScreenshotSerializer(many=True),
            400: OpenApiResponse(description="Fichier refusé (format, taille, contenu) ou champs invalides"),
        },
    )
    def post(self, request, trade_id):
        trade = self._trade(request, trade_id)
        serializer = ScreenshotUploadSerializer(
            data={
                "files": request.FILES.getlist("files"),
                "category": request.data.get("category"),
                "description": request.data.get("description", ""),
            }
        )
        serializer.is_valid(raise_exception=True)
        try:
            created = create_screenshots(
                trade=trade,
                files=serializer.validated_data["files"],
                category=serializer.validated_data["category"],
                description=serializer.validated_data["description"],
            )
        except UploadRejected as exc:
            raise ValidationError({"files": [f"{name} : {msg}" for name, msg in exc.errors]}) from exc
        except StorageError:
            return Response(
                {"detail": "Stockage indisponible. Aucun fichier n'a été enregistré."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        return Response(ScreenshotSerializer(created, many=True).data, status=status.HTTP_201_CREATED)


class ScreenshotDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Lecture, modification (catégorie, description) et suppression d'une capture."""

    serializer_class = ScreenshotSerializer
    http_method_names = ["get", "patch", "delete", "head", "options"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return TradeScreenshot.objects.none()
        return TradeScreenshot.objects.filter(trade__user=self.request.user)


class ScreenshotFileView(APIView):
    """Contenu de l'image, après contrôle de propriété. Jamais servi statiquement."""

    @extend_schema(
        responses={(200, "image/*"): OpenApiResponse(description="Fichier image")},
    )
    def get(self, request, pk):
        screenshot = get_object_or_404(
            TradeScreenshot.objects.filter(trade__user=request.user), pk=pk
        )
        storage = get_storage()
        key = screenshot.storage_key
        ext = key.rsplit(".", 1)[-1]
        content_type = CONTENT_TYPE_BY_EXT.get(ext, "application/octet-stream")

        try:
            signed = storage.signed_url(key, SIGNED_URL_TTL_SECONDS)
            if signed:
                response = HttpResponseRedirect(signed)
                response["Cache-Control"] = "private, no-store"
                return response
            handle = storage.open(key)
        except FileNotFoundInStorage as exc:
            raise Http404("Fichier introuvable.") from exc
        except StorageError:
            return Response(
                {"detail": "Stockage indisponible."}, status=status.HTTP_503_SERVICE_UNAVAILABLE
            )

        filename = re.sub(r'[^A-Za-z0-9._-]', "_", screenshot.original_filename) or "capture"
        response = FileResponse(handle, content_type=content_type)
        response["Content-Disposition"] = f'inline; filename="{filename}"'
        response["X-Content-Type-Options"] = "nosniff"
        response["Cache-Control"] = "private, max-age=3600"
        return response
