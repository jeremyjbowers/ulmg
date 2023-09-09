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
    def add_arguments(self, parser):
        parser.add_argument("--cached", action="store_true", help="Use cached data instead of downloading new data")

    def handle(self, *args, **options):
        requests.packages.urllib3.disable_warnings()

        season = utils.get_current_season()

        if not options['cached']:

            # download roster files
            print('LIVE: Download FG rosters')
            call_command('live_download_fg_rosters')

            # download mlb depth charts
            print('LIVE: Download MLB depth charts')
            call_command('live_download_mlb_depthcharts')

            # download fg stats
            print('LIVE: Download FG stats')
            call_command('live_download_fg_stats')

        # use roster files to update players who have fg_ids with mlb_ids
        print('LIVE: Crosswalk FGIDs to MLBIDs')
        call_command('live_crosswalk_fgids_to_mlbids')

        call_command('fix_dupes')

        # # use mlb depth charts to create new players
        # print('LIVE: Load players from MLB depth charts')
        # call_command('live_load_players_from_mlb_depthcharts')

        # # use mlb depth charts to update player status
        # print('LIVE: Update status from MLB depth charts')
        # call_command('live_update_status_from_mlb_depthcharts')

        # # use roster files to update players who have mlb_ids with fg_ids
        # print('LIVE: Crosswalk MLBIDs to FGIDs')
        # call_command('live_crosswalk_mlbids_to_fgids')

        # # use roster files to update all player status
        # print('LIVE: Update status from FG rosters')
        # call_command('live_update_status_from_fg_rosters')

        # # use fg stats to update all player stats
        # print('LIVE: Update stats from FG stats')
        # call_command('live_update_stats_from_fg_stats')
