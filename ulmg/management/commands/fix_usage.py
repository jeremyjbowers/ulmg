from django.core.management.base import BaseCommand, CommandError
from ulmg import models


class Command(BaseCommand):

    def handle(self, *args, **options):
        players = models.Player.objects.filter(stats__isnull=False).exclude(position="P")
        for p in players:
            if p.stats.get('pa', None):
                if int(p.stats.get('pa', 0)) > 500 and p.usage != "Unlimited":
                    print(p)