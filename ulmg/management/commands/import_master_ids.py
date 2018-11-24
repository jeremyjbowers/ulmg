import csv
import os

from django.core.management.base import BaseCommand, CommandError
from ulmg import models


class Command(BaseCommand):

    def handle(self, *args, **options):

        os.system('curl -o "data/master-ids.csv" "http://crunchtimebaseball.com/master.csv"')

        with open('data/master-ids.csv', 'r', encoding="latin-1") as readfile:
            players = [dict(d) for d in csv.DictReader(readfile)]

            for p in players:
                try:
                    obj = models.Player.objects.get(fg_id=p['fg_id'])
                    for k,v in p.items():
                        if v == "":
                            v = None
                        setattr(obj,k,v)
                    obj.save()
                    print(obj)

                except models.Player.DoesNotExist:
                    pass