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
        self.reset_players()

        self.get_hitters()
        self.get_pitchers()

        # AGGREGATE LS BY TEAM
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


    def reset_players(self):
        print("RESET")
        try:
            models.Player.objects.update(
                ls_is_mlb=False,
                ls_hr=0,
                ls_sb=0,
                ls_runs=0,
                ls_rbi=0,
                ls_avg=0,
                ls_obp=0,
                ls_slg=0,
                ls_babip=0,
                ls_wrc_plus=0,
                ls_plate_appearances=0,
                ls_iso=0,
                ls_k_pct=0,
                ls_bb_pct=0,
                ls_woba=0,
                ls_g=0,
                ls_gs=0,
                ls_ip=0,
                ls_k_9=0,
                ls_bb_9=0,
                ls_hr_9=0,
                ls_lob_pct=0,
                ls_gb_pct=0,
                ls_hr_fb=0,
                ls_era=0,
                ls_fip=0,
                ls_xfip=0,
                ls_siera=0,
                ls_xavg=0,
                ls_xwoba=0,
                ls_xslg=0,
                ls_xavg_diff=0,
                ls_xwoba_diff=0,
                ls_xslg_diff=0,
            )
            return True
        except:
            return False


    def get_hitters(self):
        print("GET: STRAT HITTERS FROM CSV")

        with open('data/2021/strat_imagined_hit.csv', 'r') as readfile:
            rows = list(csv.DictReader(readfile))

        for row in rows:
            obj = utils.fuzzy_find_player(f"{row['FIRST']} {row['LAST']}")
            if len(obj) == 1:
                obj = obj[0]
                try:
                    print(obj)
                    obj.ls_is_mlb = True
                    obj.ls_ab = int(row['IMAG AB'])
                    obj.ls_hits = int(row['IMAG H'])
                    obj.ls_2b = int(row['IMAG 2B'])
                    obj.ls_3b = int(row['IMAG 3B'])
                    obj.ls_bb = int(row['IMAG BB'])
                    obj.ls_k = int(row['IMAG K'])
                    obj.ls_plate_appearances = int(obj.ls_ab + obj.ls_bb)
                    obj.ls_hr = int(row['IMAG HR'])
                    obj.ls_rbi = int(row['IMAG RBI'])
                    obj.ls_sb = int(row['IMAG SB'])
                    obj.ls_bb_pct = Decimal( (float(obj.ls_bb) / float(obj.ls_plate_appearances)) * 100.0 )
                    obj.ls_k_pct = Decimal( (float(obj.ls_k) / float(obj.ls_plate_appearances)) * 100.0 )
                    obj.ls_avg = Decimal(row['IMAG AVG'])
                    obj.ls_obp = Decimal(row['IMAG OBP'])
                    obj.ls_slg = Decimal(row['IMAG SLG'])
                    obj.ls_iso = Decimal(obj.ls_slg - obj.ls_avg)
                    obj.save()

                except Exception as e:
                    print(e)

    def get_pitchers(self):
        print("GET: STRAT PITCHERS FROM CSV")

        with open('data/2021/strat_imagined_pitch.csv', 'r') as readfile:
            rows = list(csv.DictReader(readfile))

        for row in rows:
            obj = utils.fuzzy_find_player(f"{row['FIRST']} {row['LAST']}")
            if len(obj) == 1:
                obj = obj[0]
                try:
                    """
                    LG
                    TM
                    LAST
                    FIRST
                    IMAG W
                    IMAG L
                    IMAG ERA
                    IMAG GS
                    IMAG SV
                    IMAG IP
                    IMAG H
                    IMAG BB
                    IMAG K
                    IMAG HR
                    """
                    print(obj)
                    obj.ls_is_mlb = True
                    obj.ls_ha = int(row['IMAG H'])
                    obj.ls_hra = int(row['IMAG HR'])
                    obj.ls_pbb = int(row['IMAG BB'])
                    obj.ls_pk = int(row['IMAG K'])
                    # obj.ls_g = int()
                    obj.ls_gs = int(row['IMAG GS'])
                    obj.ls_ip = Decimal(row['IMAG IP'])
                    obj.ls_k_9 = Decimal((obj.ls_pk * 9) / obj.ls_ip)
                    obj.ls_bb_9 = Decimal((obj.ls_pbb * 9) / obj.ls_ip)
                    obj.ls_hr_9 = Decimal((obj.ls_hra * 9) / obj.ls_ip)
                    # obj.ls_babip = Decimal()
                    # obj.ls_lob_pct = Decimal()
                    # obj.ls_gb_pct = Decimal()
                    # obj.ls_hr_fb = Decimal()
                    obj.ls_era = Decimal(row['IMAG ERA'])
                    obj.ls_er = int((int(row['IMAG IP'])/9.0) * float(row['IMAG ERA']))
                    # obj.ls_fip = Decimal()
                    # obj.ls_xfip = Decimal()
                    # obj.ls_siera = Decimal()
                    obj.save()

                except Exception as e:
                    print(e)
