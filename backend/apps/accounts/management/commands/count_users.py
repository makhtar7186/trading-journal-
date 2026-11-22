from django.core.management.base import BaseCommand

from apps.accounts.models import User


class Command(BaseCommand):
    help = "Affiche le nombre de comptes (utilisé par le lanceur pour proposer la création du premier compte)."

    def handle(self, *args, **options):
        self.stdout.write(str(User.objects.count()))
