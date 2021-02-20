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
    def int_or_null(self, possible_int):
        try:
            return int(possible_int)
        except:
            return None

    def load_top_draft(self):
        with open("data/2021/top_draft_prospects.csv", "r") as readfile:
            rows = list(csv.DictReader(readfile))

        for row in rows:
            row = dict(row)
            p = utils.fuzzy_find_player(row["player"])
            if len(p) > 0:
                p = p[0]
            else:
                p = None

            if p:
                p.is_prospect = True
                p.prospect_rating_avg = Decimal(row["avg"])
                p.save()

            pr, created = models.ProspectRating.objects.get_or_create(
                year=2021, player=p, player_name=row["player"]
            )

            pr.avg = row["avg"]
            pr.med = row["med"]
            pr.mlb = self.int_or_null(row["mlb"])
            pr.ba = self.int_or_null(row["ba"])
            pr.plive = self.int_or_null(row["plive"])
            pr.p365 = self.int_or_null(row["p365"])
            pr.fg = self.int_or_null(row["fg"])
            pr.cbs = self.int_or_null(row["cbs"])

            pr.rank_type = "top-draft"

            pr.save()

    def load_top_100(self):
        with open("data/2021/top_100_prospects.csv", "r") as readfile:
            rows = list(csv.DictReader(readfile))

        for row in rows:
            row = dict(row)
            p = utils.fuzzy_find_player(row["player"])
            if len(p) > 0:
                p = p[0]
            else:
                p = None

            if p:
                p.is_prospect = True
                p.prospect_rating_avg = Decimal(row["avg"])
                p.save()

            pr, created = models.ProspectRating.objects.get_or_create(
                year=2021, player=p, player_name=row["player"]
            )

            pr.avg = row["avg"]
            pr.med = row["med"]
            pr.mlb = self.int_or_null(row["mlb"])
            pr.ba = self.int_or_null(row["ba"])
            pr.bp = self.int_or_null(row["bp"])
            pr.law = self.int_or_null(row["law"])

            pr.rank_type = "top-100"

            pr.save()

    def handle(self, *args, **options):
        models.ProspectRating.objects.all().delete()
        models.Player.objects.update(is_prospect=False)
        self.load_top_100()
        self.load_top_draft()
