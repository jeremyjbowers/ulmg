import csv

from dateutil.parser import *

from django.core.management.base import BaseCommand, CommandError
from ulmg import models


class Command(BaseCommand):

    def handle(self, *args, **options):

        with open('data/ulmg-master.csv', 'r') as readfile:
            players = [dict(p) for p in csv.DictReader(readfile)]


        for p in players:            
            for k,v in p.items():
                if v.strip() == '':
                    v = None
            del p['age']
            del p['notes']
            p['team'] = models.Team.objects.get(abbreviation=p['team'])
            p['birthdate'] = parse(p['birthdate'])
            player, created = models.Player.objects.update_or_create(**p)
            print(player, created)