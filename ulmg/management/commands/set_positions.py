import csv

from django.core.management.base import BaseCommand, CommandError
from ulmg import models


class Command(BaseCommand):

    def handle(self, *args, **options):

        with open('data/ulmg-master.csv', 'r') as readfile:
            players = list([dict(p) for p in csv.DictReader(readfile)])

        for player in players:
            print(player)
            if player['position'] in ["SS", "2B", "3B", "IF", "CI", "1B"]:
                try:
                    p = models.Player.objects.get(fangraphs_url=player['fangraphs_url'])
                except:
                    p = models.Player.objects.get(first_name=player['first_name'], last_name=player['last_name'])
                p.position = "IF"
                p.save()

            if player['position'] == "IF":
                try:
                    p = models.Player.objects.get(fangraphs_url=player['fangraphs_url'])
                except:
                    p = models.Player.objects.get(first_name=player['first_name'], last_name=player['last_name'])
                p.position = "IF"
                p.save()

            if player['position'] == "SP/1B":
                p = models.Player.objects.get(fangraphs_url=player['fangraphs_url'])
                p.position = "IF/P"
                p.save()
            
            if player['position'] == "SP/OF":
                p = models.Player.objects.get(fangraphs_url=player['fangraphs_url'])
                p.position = "OF/P"
                p.save()
