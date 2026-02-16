import csv
import ujson as json
import os

from dateutil.parser import parse
from django.apps import apps
from django.db import connection
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Count, Avg, Sum, Max, Min, Q
from django.conf import settings

from ulmg import models


class Command(BaseCommand):
    def reset_rosters(self):
        print(".... resetting rosters")
        # Reset Player model roster statuses that are still there
        models.Player.objects.filter(is_ulmg_1h_c=True).update(is_ulmg_1h_c=False)
        models.Player.objects.filter(is_ulmg_1h_p=True).update(is_ulmg_1h_p=False)
        models.Player.objects.filter(is_ulmg_1h_pos=True).update(is_ulmg_1h_pos=False)
        models.Player.objects.filter(is_ulmg_2h_c=True).update(is_ulmg_2h_c=False)
        models.Player.objects.filter(is_ulmg_2h_p=True).update(is_ulmg_2h_p=False)
        models.Player.objects.filter(is_ulmg_2h_pos=True).update(is_ulmg_2h_pos=False)
        models.Player.objects.filter(is_ulmg_reserve=True).update(is_ulmg_reserve=False)
        
        # Reset PlayerStatSeason roster statuses for current season
        from ulmg import utils
        current_season = utils.get_current_season()
        models.PlayerStatSeason.objects.filter(season=current_season).update(
            is_ulmg_mlb_roster=False,
            is_ulmg_aaa_roster=False,
            is_ulmg35man_roster=False,
            roster_status=None,
            mlb_org=None,
        )
        models.Player.objects.filter(is_owned=True).update(
            is_ulmg_35man_roster=False,
            is_ulmg_mlb_roster=False,
            is_ulmg_aaa_roster=False,
        )

    def handle(self, *args, **options):
        self.reset_rosters()