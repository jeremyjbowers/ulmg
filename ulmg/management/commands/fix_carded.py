from django.core.management.base import BaseCommand, CommandError
from ulmg import models


class Command(BaseCommand):

    def handle(self, *args, **options):
        players = models.Player.objects.filter(is_carded=True, stats__isnull=True)
        for p in players:
            p.is_carded = False
            p.save()