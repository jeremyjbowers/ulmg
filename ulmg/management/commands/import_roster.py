import csv

from django.core.management.base import BaseCommand, CommandError
from ulmg import models


class Command(BaseCommand):

    def handle(self, *args, **options):
        position_mapping = {"2B/SS": "IF","Of/1B": "OF","Utl": "UT","SP/SS": "P","LP": "P","2B": "IF","Sp": "P","3rd": "IF","3b": "IF","C": "C","RHP": "P","RF": "OF","3B/OF": "UT","1b": "IF","OF/1st": "OF","P": "P","Inf": "IF","SS/3B": "IF","SP/1B": "UT","2nd": "IF","1B": "IF","2B,SS": "IF","RP": "P","CF": "OF","INF": "IF","1B/UT": "UT","ss": "IF","SS-2b-OF": "UT","1B/C": "C","2b-SS-OF": "UT","SP-RP": "P","OF/DH": "OF","2B/3B": "IF","2b": "IF","1B/DH": "IF","1B/3B": "IF","SS": "IF","SP": "P","SWING": "P","LF": "OF","1B-OF": "UT","2B-OF": "UT","OF": "OF","IF": "IF","UT": "UT","OF/INF": "UT","1st": "IF","OF/3B": "UT","SP/RP": "P","SS/2B": "IF","C/1B": "C","SP/INF": "UT","1,2,3": "IF","DH": "HIT","2nd/SS": "IF","UTL": "UT","SWP": "P","3B": "IF","2b/ss": "IF","1b-3b": "IF","sp": "P","UTIL": "UT","LHP": "SP","SS-OF": "UT","INF/OF": "UT","1B/OF": "OF"}

        with open('data/current_roster.csv', 'r') as readfile:
            players = [dict(p) for p in csv.DictReader(readfile)]

        positions = set([p['position'] for p in players])

        for p in players:
            p['position'] = position_mapping[p['position']]
            
            for k,v in p.items():
                if v.strip() == '':
                    v = None

            player, created = models.Player.objects.update_or_create(
                name=p['name'],
                position=p['position'],
                fangraphs_id=p['fg_id'],
                team=models.Team.objects.get(abbreviation=p['team'].strip()),
                level=p['level']
            )

            print(player, created)