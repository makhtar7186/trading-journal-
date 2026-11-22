import json

from django.apps import apps
from django.core.management.base import BaseCommand

APP_LABELS = ("accounts", "trades", "strategies", "screenshots")


class Command(BaseCommand):
    help = "Affiche en JSON le nombre de lignes de chaque table métier (contrôle d'une migration de base de données)."

    def handle(self, *args, **options):
        counts = {
            model._meta.label: model.objects.count()
            for label in APP_LABELS
            for model in apps.get_app_config(label).get_models()
            if not model._meta.auto_created
        }
        self.stdout.write(json.dumps(counts, sort_keys=True))
