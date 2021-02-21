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
    season = None

    def handle(self, *args, **options):
        self.season = settings.CURRENT_SEASON
        self.team_aggregates()

    def team_aggregates(self):
        print("TEAM AGGREGATES")

        def set_hitters(team):
            for field in [
                "ls_hits",
                "ls_2b",
                "ls_3b",
                "ls_hr",
                "ls_sb",
                "ls_rbi",
                "ls_plate_appearances",
                "ls_ab",
                "ls_bb",
                "ls_k",
            ]:
                setattr(
                    team,
                    field,
                    models.Player.objects.filter(ls_is_mlb=True, team=team)
                    .exclude(position="P")
                    .aggregate(Sum(field))[f"{field}__sum"],
                )

            team.ls_avg = float(team.ls_hits) / float(team.ls_ab)
            team.ls_obp = (team.ls_hits + team.ls_bb) / float(team.ls_plate_appearances)
            teamtb = (
                (team.ls_hits - team.ls_hr - team.ls_2b - team.ls_3b)
                + (team.ls_2b * 2)
                + (team.ls_3b * 3)
                + (team.ls_hr * 4)
            )
            team.ls_slg = teamtb / float(team.ls_plate_appearances)
            team.ls_iso = team.ls_slg - team.ls_avg
            team.ls_k_pct = team.ls_k / float(team.ls_plate_appearances)
            team.ls_bb_pct = team.ls_bb / float(team.ls_plate_appearances)

        def set_pitchers(team):
            for field in [
                "ls_g",
                "ls_gs",
                "ls_ip",
                "ls_pk",
                "ls_pbb",
                "ls_ha",
                "ls_hra",
                "ls_er",
            ]:
                setattr(
                    team,
                    field,
                    models.Player.objects.filter(ls_is_mlb=True, team=team).aggregate(
                        Sum(field)
                    )[f"{field}__sum"],
                )

            team.ls_era = (team.ls_er / float(team.ls_ip)) * 9.0
            team.ls_k_9 = (team.ls_pk / float(team.ls_ip)) * 9.0
            team.ls_bb_9 = (team.ls_pbb / float(team.ls_ip)) * 9.0
            team.ls_hr_9 = (team.ls_hra / float(team.ls_ip)) * 9.0
            team.ls_hits_9 = (team.ls_ha / float(team.ls_ip)) * 9.0
            team.ls_whip = (team.ls_ha + team.ls_bb) / float(team.ls_ip)

        for team in models.Team.objects.all():
            print(f"SETTING AGGREGATES FOR {team}")
            set_hitters(team)
            set_pitchers(team)
            team.save()