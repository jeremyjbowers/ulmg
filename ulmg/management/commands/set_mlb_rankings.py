import csv

from django.core.management.base import BaseCommand, CommandError
from ulmg import models

from fuzzywuzzy import fuzz
from fuzzywuzzy import process

class Command(BaseCommand):

    def handle(self, *args, **options):
        with open('data/mlb-pro-prospects.csv', 'r') as readfile:
            all_prospects = [d for d in csv.DictReader(readfile)]

        all_players = [p.name for p in models.Player.objects.filter(level="B")]

        for prospect in all_prospects:
            name, pct = process.extractOne("%s %s" % (prospect['player_first_name'], prospect['player_last_name']), all_players)
            print(name, pct, prospect['rank'])

            try:
                p = models.Player.objects.get(name=name)
                p.mlb_prospect_rank = prospect['rank']
                p.mlb_id = prospect['player_id']
                p.mlb_url = "http://m.mlb.com/player/%s" % p.mlb_id 
                # p.mlb_prospect_rank = None
                # p.mlb_id = None
                # p.mlb_url = None
                p.save()
            except models.Player.MultipleObjectsReturned:
                print("http://m.mlb.com/player/%s" % prospect['player_id'])