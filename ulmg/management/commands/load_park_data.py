"""
{"grouping_venue_conditions":"All","key_is_year_rolling":"1","key_year":"2021","key_bat_side":"All","venue_id":"1","venue_name":"Angel Stadium","main_team_id":"108","name_display_club":"Angels","n_pa":"16531","index_runs":"104","index_hardhit":"105","index_woba":"102","index_wobacon":"103","index_xwobacon":"102","index_xbacon":"101","index_obp":"102","index_so":"101","index_bb":"105","index_bacon":"103","index_hits":"102","index_1b":"102","index_2b":"97","index_3b":"87","index_hr":"108","year_range":"2019-2021","venue_url":"https:\/\/baseballsavant.mlb.com\/leaderboard\/statcast-venue?venueId=1"}
"""


import csv
import glob
import json
import os

from django.apps import apps
from django.db import connection
from django.db.models import Avg, Sum, Count
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings

from ulmg import models, utils


class Command(BaseCommand):
    def handle(self, *args, **options):
        season = utils.get_current_season()
        venues = glob.glob(f"data/parks/{season}/*.json")

        for venue_path in venues:
            with open(venue_path, 'r') as readfile:
                venue_dict = json.loads(readfile.read())

                defaults = {
                    "mlb_venue_url": venue_dict['venue_url'].replace('\/', '/'),
                    "park_factor": venue_dict['index_woba'],
                    "pf_wobacon": venue_dict['index_xwobacon'],
                    "pf_bacon": venue_dict['index_bacon'],
                    "pf_runs": venue_dict['index_runs'],
                    "pf_obp": venue_dict['index_obp'],
                    "pf_h": venue_dict['index_hits'],
                    "pf_1b": venue_dict['index_1b'],
                    "pf_2b": venue_dict['index_2b'],
                    "pf_3b": venue_dict['index_3b'],
                    "pf_hr": venue_dict['index_hr'],
                    "pf_bb": venue_dict['index_bb'],
                    "pf_so": venue_dict['index_so'],
                    "pf_years": venue_dict['year_range'],
                    "pf_pa": venue_dict['n_pa'],
                    "name": venue_dict['venue_name'],
                    "mlb_team": venue_dict['name_display_club']
                }

                obj, created = models.Venue.objects.update_or_create(
                    mlb_venue_id=venue_dict['venue_id'],
                    defaults=defaults
                )

                print(obj, created)