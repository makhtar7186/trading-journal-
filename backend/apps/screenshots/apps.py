from django.apps import AppConfig


class ScreenshotsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.screenshots"

    def ready(self):
        from . import signals  # noqa: F401
