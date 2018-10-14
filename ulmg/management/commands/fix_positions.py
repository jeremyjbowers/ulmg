from django.core.management.base import BaseCommand, CommandError
from ulmg import models


class Command(BaseCommand):

    def handle(self, *args, **options):
        players = models.Player.objects.filter(position__in=["IF/OF", "OF/P", "IF/P", "DH"])
        for p in players:
            if p.position in ["IF/OF", "DH"]:
                p.position = "IF-OF"
            if p.position == "OF/P":
                p.position = "OF-P"
            if p.position == "IF/P":
                p.position = "IF-P"
            p.save()

        players = models.Player.objects.filter(position__isnull=True)
        for p in players:
            print(p)
            p.position = "IF-OF"
            p.save()