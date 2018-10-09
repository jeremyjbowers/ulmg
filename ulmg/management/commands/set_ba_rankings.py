import csv

from django.core.management.base import BaseCommand, CommandError
from ulmg import models


from fuzzywuzzy import fuzz
from fuzzywuzzy import process

class Command(BaseCommand):

    def handle(self, *args, **options):
        with open('data/ba_pro_prospects.scraped.csv', 'r') as readfile:
            all_prospects = [d for d in csv.DictReader(readfile)]

        all_players = [p.name for p in models.Player.objects.filter(level="B")]

        for prospect in all_prospects:
            name, pct = process.extractOne(prospect['name'], all_players)
            print(name, pct, prospect['rank'])

            try:
                p = models.Player.objects.get(name=name)
                p.ba_prospect_rank = prospect['rank']
                p.ba_url = prospect['url']
                p.ba_id = prospect['id']
                p.save()
            except models.Player.MultipleObjectsReturned:
                print(prospect['url'])