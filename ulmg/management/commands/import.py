import csv
import json
import os

from dateutil.parser import parse
from django.apps import apps
from django.db import connection
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError

from ulmg import models


class Command(BaseCommand):

    def handle(self, *args, **options):
        with open('data/ulmg/historical-drafts.csv', 'r') as readfile:
            picks = [dict(c) for c in csv.DictReader(readfile)]

        models.DraftPick.objects.filter(year=2018).delete()

        for p in picks:
            for k,v in p.items():

                if v == "":
                    p[k] = None

                if k == "original_team" and v:
                    p[k] = models.Team.objects.get(abbreviation=v)

                if k in ['draft_round', 'pick_number']:
                    p[k] = int(v)

            p['team'] = models.Team.objects.get(abbreviation=p['team_name'])

            obj, created = models.DraftPick.objects.get_or_create(**p)
            print(obj, created)