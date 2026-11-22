from django.contrib import admin

from .models import Trade


@admin.register(Trade)
class TradeAdmin(admin.ModelAdmin):
    list_display = ("name", "asset", "direction", "status", "realized_rr", "trade_date", "user")
    list_filter = ("status", "market_type", "direction")
    search_fields = ("name", "asset")
