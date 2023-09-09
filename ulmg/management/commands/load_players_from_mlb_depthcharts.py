from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from django.db.models import Count

import ujson as json

from ulmg import models, utils

class Command(BaseCommand):

    def handle(self, *args, **options):

        with open('data/rosters/all_mlb_rosters.json', 'r') as readfile:
            players = json.loads(readfile.read())

            for p in players:
                try:
                    obj = models.Player.objects.get(mlbam_id=p['mlbam_id'])

                except models.Player.DoesNotExist:
                    # this is where we need to do stuff
                    # maybe it should just save them to a file I can check?
                    # or create stub versions I can verify?

                    pass