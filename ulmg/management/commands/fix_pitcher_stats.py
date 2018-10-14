from django.core.management.base import BaseCommand, CommandError
from ulmg import models


class Command(BaseCommand):

    def handle(self, *args, **options):
        players = models.Player.objects.filter(position="P", stats__isnull=False)
        for p in players:
            if not p.stats.get('ip', None):
                p.stats = None
                p.save()