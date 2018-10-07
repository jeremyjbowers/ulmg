import csv

from dateutil.parser import *

from django.core.management.base import BaseCommand, CommandError
from ulmg import models


class Command(BaseCommand):

    def handle(self, *args, **options):

        existing = set([p['fangraphs_url'] for p in models.Player.objects.all().values('fangraphs_url')])

        with open('data/fg_hitters.scraped.csv', 'r') as readfile:
            hitters = [dict(p) for p in csv.DictReader(readfile)]

        with open('data/fg_pitchers.scraped.csv', 'r') as readfile:
            pitchers = [dict(p) for p in csv.DictReader(readfile)]

        players = hitters+pitchers

        for player in players:
            if player['url'] not in existing:
                print(player)
                p = models.Player(
                    name=player['name'],
                    id=player['id'],
                    fangraphs_url=player['url']
                )
                position = p.fangraphs_url.split('position=')[1]
                if "/" in position:
                    position = position.split("/")[0]
                elif position in ['1B','2B','3B','SS']:
                    p.position = "IF"
                elif position in ['OF','CF','RF','LF']:
                    p.position = "OF"
                else:
                    p.position = position

                p.owned = False
                p.save()