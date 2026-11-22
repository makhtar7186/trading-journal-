import uuid

from django.db import models


class ScreenshotCategory(models.TextChoices):
    BEFORE = "BEFORE", "Avant le trade"
    DURING = "DURING", "Pendant le trade"
    AFTER = "AFTER", "Après le trade"


class TradeScreenshot(models.Model):
    """Métadonnées d'une capture. Le fichier lui-même vit dans le stockage (jamais en base)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    trade = models.ForeignKey(
        "trades.Trade", on_delete=models.CASCADE, related_name="screenshots"
    )
    # Clé interne générée par le serveur ; jamais exposée par l'API.
    storage_key = models.CharField(max_length=255, unique=True)
    original_filename = models.CharField(max_length=255)
    category = models.CharField(max_length=6, choices=ScreenshotCategory.choices)
    description = models.CharField(max_length=500, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["uploaded_at", "id"]
        indexes = [models.Index(fields=["trade", "category"])]

    def __str__(self):
        return f"{self.original_filename} ({self.category})"
