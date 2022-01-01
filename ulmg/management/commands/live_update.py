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
        requests.packages.urllib3.disable_warnings()

        season = utils.get_current_season()

        script_info = {
            "season": season,
            "timestamp": utils.generate_timestamp(),
            "hostname": utils.get_hostname(),
            "scriptname": utils.get_scriptname(),
        }

        utils.get_fg_roster_files()
        utils.import_players_from_rosters()
        utils.parse_roster_info()

        utils.get_fg_minor_season(**script_info)
        utils.get_fg_major_hitter_season(**script_info)
        utils.get_fg_major_pitcher_season(**script_info)
        # utils.aggregate_team_stats_season(**script_info)
