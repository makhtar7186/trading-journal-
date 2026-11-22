from django.urls import path

from . import views

urlpatterns = [
    path("analytics/overview/", views.OverviewView.as_view(), name="analytics-overview"),
    path("analytics/performance/", views.PerformanceView.as_view(), name="analytics-performance"),
    path("analytics/equity-curve/", views.EquityCurveView.as_view(), name="analytics-equity-curve"),
    path("analytics/by-asset/", views.ByAssetView.as_view(), name="analytics-by-asset"),
    path("analytics/by-market/", views.ByMarketView.as_view(), name="analytics-by-market"),
    path("analytics/by-strategy/", views.ByStrategyView.as_view(), name="analytics-by-strategy"),
    path("analytics/calendar/", views.CalendarView.as_view(), name="analytics-calendar"),
    path("analytics/by-period/", views.ByPeriodView.as_view(), name="analytics-by-period"),
]
