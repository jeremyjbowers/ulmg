import csv
import json
import os
from decimal import Decimal

from dateutil.parser import parse
from django.apps import apps
from django.db import connection
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from nameparser import HumanName

from ulmg import models
from ulmg import utils


class Command(BaseCommand):
    def handle(self, *args, **options):

        def int_or_null(possible_int):
            try:
                return int(possible_int)
            except:
                return None

        models.ProspectRating.objects.all().delete()

        with open("data/2021/top_100_prospects.csv", "r") as readfile:
            rows = list(csv.DictReader(readfile))

        for row in rows:
            row = dict(row)
            p = utils.fuzzy_find_player(row['player'])
            if len(p) > 0 and "Luis Garcia" not in row['player']:
                p = p[0]

                pr, created = models.ProspectRating.objects.get_or_create(
                    year=2021,
                    player=p
                )                    

                pr.skew = row['skew']
                pr.avg = row['avg']
                pr.med = row['med']
                pr.mlb = int_or_null(row['mlb'])
                pr.ba = int_or_null(row['ba'])
                pr.bp = int_or_null(row['bp'])
                pr.law = int_or_null(row['law'])

                pr.save()

            else:
                print(row)