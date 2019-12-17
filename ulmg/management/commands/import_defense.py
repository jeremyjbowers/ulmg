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

            models.Player.objects.exclude(position="P").update(defense=[])
            with open(f'data/defense/{year}-som-range.csv', 'r') as readfile:
                players = [dict(c) for c in csv.DictReader(readfile)]

                for p in players:
                    obj = models.Player.objects.filter(name__search="%s %s" % (p['FIRST'], p['LAST'])).exclude(position="P")
                    if len(obj) == 1:
                        obj = obj[0]
                        if not obj.defense:
                            obj.defense = []
                        defense = set()
                        for pos in ["C-2", "1B-3", "2B-4", "3B-5", "SS-6", "RF-9", "CF-8", "LF-7"]:
                            if p[pos.split('-')[0]] != "":
                                rating = p[pos.split('-')[0]]
                                if "(" in rating:
                                    rating = rating.split("(")[0]
                                d = f"{pos}-{rating}"
                                defense.add(d)
                        obj.defense = list(defense)
                        inf = False
                        of = False
                        c = False
                        for p in obj.defense:
                            if "C-" in p:
                                c = True
                            if "F-" in p:
                                of = True
                            if "B-" in p:
                                inf = True
                            if "SS" in p:
                                inf = True

                            if inf == True:
                                obj.position = "IF"

                            if of == True:
                                obj.position = "OF"

                            if inf == True and of == True:
                                obj.position = "IF-OF"

                            if c == True:
                                obj.position = "C"

                        if obj.defense == []:
                            obj.position = "DH"

                        obj.save()
                        print(obj.name, obj.defense)