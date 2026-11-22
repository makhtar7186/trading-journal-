from django.urls import path

from .views import ScreenshotDetailView, ScreenshotFileView, TradeScreenshotListCreateView

urlpatterns = [
    path(
        "trades/<uuid:trade_id>/screenshots/",
        TradeScreenshotListCreateView.as_view(),
        name="trade-screenshots",
    ),
    path("screenshots/<uuid:pk>/", ScreenshotDetailView.as_view(), name="screenshot-detail"),
    path("screenshots/<uuid:pk>/file/", ScreenshotFileView.as_view(), name="screenshot-file"),
]
