import csv
import json
import os
from decimal import Decimal

from bs4 import BeautifulSoup
from dateutil.parser import parse
from django.apps import apps
from django.db import connection
from django.db.models import Avg, Sum, Count
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
import requests

from ulmg import models
from ulmg import utils


class Command(BaseCommand):

    def fix(self, name_string):
        return name_string.replace('*', '').replace('-', '').replace('+', '').replace(' Jr', '').lower()

    team_mapping = {
        "TEA": "TEX",
        "SLN": "STL",
        "TOA": "TOR",
        "WAN": "WAS",
        "SFN": "SFG",
        "SEA": "SEA",
        "KCA": "KCA",
        "CHN": "CHC",
        "CLA": "CLE",
        "LAA": "LAA",
        "NYN": "NYM",
        "OAA": "OAK",
        "SDN": "SDP",
        "TBA": "TBR",
        "PHN": "PHI",
        "ATN": "ATL",
        "BOA": "BOS",
        "MNA": "MIN",
        "PIN": "PIT",
        "CHA": "CHA",
        "LAN": "LAD",
        "NYA": "NYY",
        "DEA": "DET",
        "MMN": "MIA",
        "MLN": "MIL",
        "HOA": "HOU",
        "CIN": "CIN",
        "CON": "COL",
        "BAA": "BAL",
        "ARN": "ARI"
    }

    def load_hitters(self):

        with open("data/2021/strat_cards_hit.csv", "r") as readfile:
            rows = [dict(a) for a in csv.DictReader(readfile)]

        for row in rows:
            tm = self.team_mapping.get(row['TM'], None)
            last = self.fix(row['HITTERS'].split(',')[0])
            first_i = self.fix(row['HITTERS'].split(',')[1])
            if tm:
                try:
                    p = models.Player.objects.get(last_name__istartswith=last, first_name__istartswith=first_i)
                except Exception as e:
                    print(e, row)

    def handle(self, *args, **options):
        self.load_hitters()