import uuid

from django.conf import settings
from django.db import models


class Strategy(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="strategies"
    )
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    entry_rules = models.TextField(blank=True)
    exit_rules = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "strategies"
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["user", "name"], name="uniq_strategy_user_name"),
        ]
        indexes = [models.Index(fields=["user", "is_active"])]

    def __str__(self):
        return self.name
