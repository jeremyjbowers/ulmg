import csv
import json
import os
from decimal import Decimal

from dateutil.parser import parse
from django.apps import apps
from django.db import connection
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError

from ulmg import models


class Command(BaseCommand):

    def handle(self, *args, **options):
        models.LiveStat.objects.all().delete()

        with open('data/fg_hit.csv', 'r') as readfile:
            hitters = [dict(c) for c in csv.DictReader(readfile)]

        with open('data/fg_pitch.csv', 'r') as readfile:
            pitchers = [dict(c) for c in csv.DictReader(readfile)]

        for h in hitters:
            try:
                obj = models.Player.objects.get(fg_id=h['playerid'])
                ls = models.LiveStat(
                    player=obj,
                    hitter=True,
                    season=2018,
                    level="MLB",
                    wrc_plus=Decimal(h['wRC+']),
                    plate_appearances=int(h['PA']),
                    iso=Decimal(h['ISO']),
                    k_pct=Decimal(h['K%'].replace(' %', '')),
                    bb_pct=Decimal(h['BB%'].replace(' %', '')),
                    woba=h['wOBA']
                )
                ls.save()
            except:
                print(h)
