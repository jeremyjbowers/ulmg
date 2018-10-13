from django.core.management.base import BaseCommand, CommandError
from ulmg import models


class Command(BaseCommand):

    def handle(self, *args, **options):
        players = models.Player.objects.filter(position="UT")
        for p in players:
            p.position="IF/OF"
            p.save()