# ABOUTME: ARCHIVED - Original load_players_from_mlb_depthcharts. See documents/MLB_DATA_PIPELINE_RECOMMENDATION.md
# ABOUTME: Reads all_mlb_rosters.json (never created) - was a stub that did nothing.
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
                    pass
