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

        with open('data/ba_col_prospects.scraped.csv', 'r') as readfile:
            college = [dict(p) for p in csv.DictReader(readfile)]

        with open('data/ba_hs_prospects.scraped.csv', 'r') as readfile:
            hs = [dict(p) for p in csv.DictReader(readfile)]

        players = hs + college

        for player in players:
            try:
                p = models.Player.objects.get(name=player['name'])
                p.ba_id = player['id']
                p.ba_url = player['url']
                p.draft_eligibility_year = "2018"
                p.ba_draft_rank = make_none(player['rank'])
                p.is_amateur = True
                p.is_prospect = True
                print("Found %s" % p)
                p.save()

            except models.Player.DoesNotExist:
                try:
                    p = models.Player(
                        name=player['name'],
                        ba_id=player['id'],
                        ba_url=player['url'],
                        ba_draft_rank=make_none(player['rank']),
                        draft_eligibility_year="2018",
                        is_amateur=True,
                        level="B",
                        is_prospect=True
                    )
                    if "/" in player['pos']:
                        position = player['pos'].split('/')[0]
                    else:
                        position = player['pos']

                    if position in ['1B', '2B', '3B', 'SS']:
                        p.position = "IF"
                    elif position in ['RHP', 'LHP']:
                        p.position = "P"
                    else:
                        p.position = position
                    print("New %s" % p)
                    p.save()
                except:
                    errors.append(player)

        with open('data/errors/import_ba_draft_prospects.errors.json', 'w') as writefile:
            writefile.write(json.dumps(errors))