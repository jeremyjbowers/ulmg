import csv
import json

from dateutil.parser import *

from django.core.management.base import BaseCommand, CommandError
from ulmg import models


class Command(BaseCommand):

    def handle(self, *args, **options):
        def make_none(rank):
            if rank == "":
                return None
            return int(rank)

        errors = []

        with open('data/fg_pro_prospects.scraped.csv', 'r') as readfile:
            players = [dict(p) for p in csv.DictReader(readfile)]

            for player in players:
                try:
                    p = models.Player.objects.get(fangraphs_id=player['id'])
                    if player['pos'] in ['OF', 'LF', 'CF', 'RF']:
                        p.position = "OF"
                    elif player['pos'] == "C":
                        p.position = "C"
                    elif player['pos'] in ['LHP', 'RHP']:
                        p.position = "P"
                    p.fg_prospect_rank=make_none(player['rank'])
                    p.fg_prospect_fv=player['fv']
                    p.save()

                except models.Player.DoesNotExist:
                    try:
                        p = models.Player(
                            name=player['name'],
                            fangraphs_id=player['id'],
                            fangraphs_url=player['url'].split('&position=')[0],
                            fg_prospect_fv=player['fv'],
                            fg_prospect_rank=player['rank'],
                            level="B",
                        )
                        if "/" in player['pos']:
                            position = player['pos'].split('/')[0]
                        else:
                            position = player['pos']

                        if position in ['1B', '2B', '3B', 'SS']:
                            p.position = "IF"
                        else:
                            p.position = position
                        print(player)
                        p.save()
                    except:
                        errors.append(player)

        with open('data/errors/import_prospects.errors.json', 'w') as writefile:
            writefile.write(json.dumps(errors))