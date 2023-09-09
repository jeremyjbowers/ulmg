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

from ulmg import models, utils


class Command(BaseCommand):
    def handle(self, *args, **options):
        teams = settings.ROSTER_TEAM_IDS

        for team_id, team_abbrev, team_name in teams:
            url = f"https://cdn.fangraphs.com/api/depth-charts/roster?teamid={team_id}"
            roster = requests.get(url, verify=False).json()
            with open(f"data/rosters/{team_abbrev}_roster.json", "w") as writefile:
                writefile.write(json.dumps(roster))