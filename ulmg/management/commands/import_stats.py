import csv
import json

from django.core.management.base import BaseCommand, CommandError

from ulmg import models


class Command(BaseCommand):

    def handle(self, *args, **options):

        does_not_exist = []
        multiple = []

        with open('data/fg_hitters.scraped.csv', 'r') as readfile:
            hitters = [dict(p) for p in csv.DictReader(readfile)]

        with open('data/fg_pitchers.scraped.csv', 'r') as readfile:
            pitchers = [dict(p) for p in csv.DictReader(readfile)]

        players = hitters+pitchers

        for player in players:
            print(player['name'])
            playerid = str(player['id'])

            try:
                p = models.Player.objects.get(fangraphs_id=playerid)
                p.stats = player
                p.save()

            except models.Player.DoesNotExist:
                does_not_exist.append(player)

            except models.Player.MultipleObjectsReturned:
                multiple.append(player)

        with open('data/does_not_exist.json','w') as writefile:
            writefile.write(json.dumps(does_not_exist))

        with open('data/multiple.json', 'w') as writefile:
            writefile.write(json.dumps(multiple))
