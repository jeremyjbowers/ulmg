from django.core.management.base import BaseCommand, CommandError
from ulmg import models


class Command(BaseCommand):

    def handle(self, *args, **options):
        # prospects weirdly get a different URL
        # no idea what happens to these in the FUTURE
        # probably redirects.
        # fix that when we get to it.
        players = models.Player.objects.filter(bbref_id__contains="player.fcgi?id=")

        for p in players:
            p.bbref_id = p.bbref_id.split("player.fcgi?id=")[1]
            p.save()