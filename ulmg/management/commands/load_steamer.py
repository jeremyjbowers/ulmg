import csv
import json
import os
from decimal import Decimal

from bs4 import BeautifulSoup
from dateutil.parser import parse
from django.apps import apps
from django.db import connection
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
import requests

from ulmg import models


class Command(BaseCommand):
    season = None

    def handle(self, *args, **options):
        self.season = settings.CURRENT_SEASON
        self.get_hitters()
        self.get_pitchers()

    def get_hitters(self):
        with open('data/2020/steamer_hit.csv', 'r') as readfile:
            players = [dict(p) for p in csv.DictReader(readfile) if int(p['PA']) >= 5]
            print('Loading %s hitters ...' % len(players))
            for p in players:
                obj = models.Player.objects.filter(fg_id=p['playerid'])
                if len(obj) == 1:
                    obj = obj[0]                    
                    obj.ps_stat_origin = "Steamer"
                    obj.ps_is_mlb = True
                    obj.ps_g = int(p['G'])
                    obj.ps_pa = int(p['PA'])
                    obj.ps_hr = int(p['HR'])
                    obj.ps_bb = int(p['BB'])
                    obj.ps_k = int(p['SO'])
                    obj.ps_sb = int(p['SB'])
                    obj.ps_cs = int(p['CS'])
                    obj.ps_avg = Decimal(p['AVG'])
                    obj.ps_obp = Decimal(p['OBP'])
                    obj.ps_slg = Decimal(p['SLG'])
                    obj.ps_ops = Decimal(p['OPS'])
                    obj.ps_woba = Decimal(p['wOBA'])
                    obj.ps_wrc_plus = int(p['wRC+'])
                    obj.ps_bsr = Decimal(p['BsR'])
                    obj.ps_fld = Decimal(p['Fld'])
                    obj.ps_off = Decimal(p['Off'])
                    obj.ps_def = Decimal(p['Def'])
                    obj.ps_war = Decimal(p['WAR'])
                    obj.save()

    def get_pitchers(self):
        with open('data/2020/steamer_pitch.csv', 'r') as readfile:
            players = [dict(p) for p in csv.DictReader(readfile) if int(p['IP'].split(".")[0]) >= 5]
            print('Loading %s pitchers ...' % len(players))
            for p in players:
                obj = models.Player.objects.filter(fg_id=p['playerid'])
                if len(obj) == 1:
                    obj = obj[0]
                    obj.ps_stat_origin = "Steamer"
                    obj.ps_is_mlb = True
                    obj.ps_g = int(p['G'])
                    obj.ps_era = Decimal(p['ERA'])
                    obj.ps_fip = Decimal(p['FIP'])
                    obj.ps_gs = int(p['GS'])
                    obj.ps_sv = int(p['SV'])
                    obj.ps_ip = int(p['IP'].split('.')[0])
                    obj.ps_h = int(p['H'])
                    obj.ps_er = int(p['ER'])
                    obj.ps_hr = int(p['HR'])
                    obj.ps_so = int(p['SO'])
                    obj.ps_bb = int(p['BB'])
                    obj.ps_whip = Decimal(p['WHIP'])
                    obj.ps_k_9 = Decimal(p['K/9'])
                    obj.ps_bb_9 = Decimal(p['BB/9'])
                    obj.ps_ra9_war = Decimal(p['RA9-WAR'])
                    obj.ps_war = Decimal(p['WAR'])
                    obj.save()
