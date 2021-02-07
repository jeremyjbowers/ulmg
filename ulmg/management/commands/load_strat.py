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
        models.Player.objects.update(
            ls_is_mlb=False,
            is_carded=False,
            ls_hits=0,
            ls_2b=0,
            ls_3b=0,
            ls_ab=0,
            ls_hr=0,
            ls_sb=0,
            ls_runs=0,
            ls_rbi=0,
            ls_k=0,
            ls_bb=0,
            ls_avg=Decimal(0.0),
            ls_obp=Decimal(0.0),
            ls_slg=Decimal(0.0),
            ls_babip=Decimal(0.0),
            ls_wrc_plus=0,
            ls_plate_appearances=0,
            ls_iso=Decimal(0.0),
            ls_k_pct=Decimal(0.0),
            ls_bb_pct=Decimal(0.0),
            ls_woba=Decimal(0.0),
            ls_g=0,
            ls_gs=0,
            ls_ip=Decimal(0.0),
            ls_pk=0,
            ls_pbb=0,
            ls_ha=0,
            ls_hra=0,
            ls_er=0,
            ls_k_9=Decimal(0.0),
            ls_bb_9=Decimal(0.0),
            ls_hr_9=Decimal(0.0),
            ls_lob_pct=Decimal(0.0),
            ls_gb_pct=Decimal(0.0),
            ls_hr_fb=Decimal(0.0),
            ls_era=Decimal(0.0),
            ls_fip=Decimal(0.0),
            ls_xfip=Decimal(0.0),
            ls_siera=Decimal(0.0),
            ls_xavg=Decimal(0.0),
            ls_xwoba=Decimal(0.0),
            ls_xslg=Decimal(0.0),
            ls_xavg_diff=Decimal(0.0),
            ls_xwoba_diff=Decimal(0.0),
            ls_xslg_diff=Decimal(0.0),
        )

    def get_hitters(self):
        print("GET: STRAT HITTERS FROM CSV")

        with open("data/2021/strat_imagined_hit.csv", "r") as readfile:
            rows = list(csv.DictReader(readfile))

        for row in rows:
            obj = utils.fuzzy_find_player(f"{row['FIRST']} {row['LAST']}")
            if len(obj) > 0:
                obj = obj[0]
                try:
                    print(obj)
                    obj.ls_is_mlb = True
                    obj.is_carded = True
                    obj.ls_ab = obj.ls_ab + int(row["IMAG AB"])
                    obj.ls_hits = obj.ls_hits + int(row["IMAG H"])
                    obj.ls_2b = obj.ls_2b + int(row["IMAG 2B"])
                    obj.ls_3b = obj.ls_3b + int(row["IMAG 3B"])
                    obj.ls_bb = obj.ls_bb + int(row["IMAG BB"])
                    obj.ls_k = obj.ls_k + int(row["IMAG K"])
                    obj.ls_plate_appearances = int(obj.ls_ab + obj.ls_bb)
                    obj.ls_hr = obj.ls_hr + int(row["IMAG HR"])
                    obj.ls_rbi = obj.ls_rbi + int(row["IMAG RBI"])
                    obj.ls_sb = obj.ls_sb + int(row["IMAG SB"])
                    obj.ls_bb_pct = Decimal(
                        (float(obj.ls_bb) / float(obj.ls_plate_appearances)) * 100.0
                    )
                    obj.ls_k_pct = Decimal(
                        (float(obj.ls_k) / float(obj.ls_plate_appearances)) * 100.0
                    )
                    obj.ls_avg = Decimal((obj.ls_hits / float(obj.ls_ab)))
                    obj.ls_obp = Decimal(
                        ((obj.ls_bb + obj.ls_hits) / float(obj.ls_plate_appearances))
                    )
                    tb = (
                        (obj.ls_hits - obj.ls_2b - obj.ls_3b - obj.ls_hr)
                        + (2 * obj.ls_2b)
                        + (3 * obj.ls_3b)
                        + (4 * obj.ls_hr)
                    )
                    obj.ls_slg = Decimal((tb / float(obj.ls_ab)))
                    obj.ls_iso = Decimal(obj.ls_slg - obj.ls_avg)
                    obj.save()

                except Exception as e:
                    print(e)

    def get_pitchers(self):
        print("GET: STRAT PITCHERS FROM CSV")

        with open("data/2021/strat_imagined_pitch.csv", "r") as readfile:
            rows = list(csv.DictReader(readfile))

        for row in rows:
            obj = utils.fuzzy_find_player(f"{row['FIRST']} {row['LAST']}")
            if len(obj) > 0:
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
                    obj.is_carded = True
                    obj.ls_ha = obj.ls_ha + int(row["IMAG H"])
                    obj.ls_hra = obj.ls_hra + int(row["IMAG HR"])
                    obj.ls_pbb = obj.ls_pbb + int(row["IMAG BB"])
                    obj.ls_pk = obj.ls_pk + int(row["IMAG K"])
                    # obj.ls_g = int()
                    obj.ls_gs = obj.ls_gs + int(row["IMAG GS"])
                    obj.ls_ip = obj.ls_ip + Decimal(row["IMAG IP"])
                    obj.ls_k_9 = Decimal((obj.ls_pk * 9) / obj.ls_ip)
                    obj.ls_bb_9 = Decimal((obj.ls_pbb * 9) / obj.ls_ip)
                    obj.ls_hr_9 = Decimal((obj.ls_hra * 9) / obj.ls_ip)
                    # obj.ls_babip = Decimal()
                    # obj.ls_lob_pct = Decimal()
                    # obj.ls_gb_pct = Decimal()
                    # obj.ls_hr_fb = Decimal()
                    # obj.ls_era = Decimal(row["IMAG ERA"])
                    obj.ls_er = obj.ls_er + int(
                        (int(row["IMAG IP"]) / 9.0) * float(row["IMAG ERA"])
                    )
                    try:
                        obj.ls_era = Decimal((9 * obj.ls_er) / float(obj.ls_ip))
                    except:
                        obj.ls_era = Decimal(999)
                    # obj.ls_fip = Decimal()
                    # obj.ls_xfip = Decimal()
                    # obj.ls_siera = Decimal()
                    obj.save()

                except Exception as e:
                    print(e)
