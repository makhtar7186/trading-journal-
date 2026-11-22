from django.contrib import admin

from .models import TradeScreenshot


@admin.register(TradeScreenshot)
class TradeScreenshotAdmin(admin.ModelAdmin):
    list_display = ("original_filename", "category", "trade", "uploaded_at")
    list_filter = ("category",)
    # Le fichier n'est pas modifiable depuis l'admin : seules les métadonnées le sont.
    readonly_fields = ("storage_key", "trade", "original_filename", "uploaded_at")
