from django.conf import settings
from django.urls import reverse
from rest_framework import serializers

from .models import ScreenshotCategory, TradeScreenshot


class ScreenshotSerializer(serializers.ModelSerializer):
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = TradeScreenshot
        fields = [
            "id",
            "trade",
            "original_filename",
            "category",
            "description",
            "uploaded_at",
            "file_url",
        ]
        # Seuls la catégorie et la description sont modifiables ; storage_key n'est jamais exposée.
        read_only_fields = ["id", "trade", "original_filename", "uploaded_at"]

    def get_file_url(self, obj) -> str:
        return reverse("screenshot-file", args=[obj.pk])


class ScreenshotUploadSerializer(serializers.Serializer):
    files = serializers.ListField(
        child=serializers.FileField(allow_empty_file=False),
        allow_empty=False,
        write_only=True,
    )
    category = serializers.ChoiceField(choices=ScreenshotCategory.choices)
    description = serializers.CharField(required=False, allow_blank=True, max_length=500, default="")

    def validate_files(self, value):
        limit = settings.SCREENSHOT_MAX_FILES_PER_REQUEST
        if len(value) > limit:
            raise serializers.ValidationError(f"Maximum {limit} fichiers par envoi.")
        return value
