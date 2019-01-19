import csv
import os

from django.apps import apps
from django.db import connection
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError

from ulmg import models


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument('year', type=str)

    def handle(self, *args, **options):
        year = options.get('year', None)
    
        if year:
            with open(f'data/defense/{year}-som-range.csv', 'r') as readfile:
                players = [dict(c) for c in csv.DictReader(readfile)]

                for p in players:
                    obj = models.Player.objects.filter(name__search=p['name']).exclude(position="P")
                    if len(obj) == 1:
                        obj = obj[0]
                        if not obj.defense:
                            obj.defense = []
                        for pos in ["C", "1B", "2B", "3B", "SS", "RF", "CF", "LF"]:
                            if p[pos] != "":
                                rating = p[pos]
                                if "(" in rating:
                                    rating = rating.split("(")[0]
                                d = f"{pos}{rating}"
                                obj.defense.append(d)
                    obj.save()
                    print(obj.name, obj.defense)