import csv
import os

from django.core.management.base import BaseCommand, CommandError
from ulmg import models


class Command(BaseCommand):

    def handle(self, *args, **options):
        with open('data/champions.csv', 'r', encoding="utf-8") as readfile:
            champs = [dict(c) for c in csv.DictReader(readfile)]

        for c in champs:

            try:
                t = models.Team.objects.get(owner=c['owner'])
                if t.championships:
                    cs = list(t.championships)
                    cs.append(c['year'])
                    t.championships = sorted(list(set(cs)), key=lambda x:x)
                else:
                    t.championships = [c['year']]
                t.save()
                print(c['year'], c['owner'], t)

            except models.Team.DoesNotExist:
                print('NOPE %(year)s %(owner)s' % c)
            