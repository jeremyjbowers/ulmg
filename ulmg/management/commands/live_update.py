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

    def get_results(self, url):
        r = requests.get(url)
        soup = BeautifulSoup(r.text, 'lxml')
        return soup.select('#LeaderBoard1_dg1_ctl00 tbody tr')

    def get_hitters(self):
        url = f"https://www.fangraphs.com/leaders.aspx?pos=all&stats=bat&lg=all&qual=10&type=8&season={self.season}&month=0&season1={self.season}&ind=0&team=0&rost=0&age=0&filter=&players=0&startdate=&enddate=&page=1_1500"

        rows = self.get_results(url)

        for row in rows:
            h = row.select('td')
            ls_dict = {}

            try:
                obj = models.Player.objects.get(fg_id=h[1].select('a')[0].attrs['href'].split('playerid=')[1].split('&')[0])
                obj.ls_plate_appearances = int(h[4].text.strip())
                obj.ls_hr = int(h[5].text.strip())
                obj.ls_sb = int(h[8].text.strip())
                obj.ls_bb_pct = Decimal(h[9].text.replace(' %', '').strip())
                obj.ls_k_pct = Decimal(h[10].text.replace(' %', '').strip())
                obj.ls_iso = Decimal(h[11].text.strip())
                obj.ls_babip = Decimal(h[12].text.strip())
                obj.ls_avg = Decimal(h[13].text.strip())
                obj.ls_obp = Decimal(h[14].text.strip())
                obj.ls_slg = Decimal(h[15].text.strip())
                obj.ls_woba = Decimal(h[16].text.strip())
                obj.ls_wrc_plus = Decimal(h[17].text.strip())
                obj.save()

            except Exception as e:
                print("%s\n  name: %s\n  fg_id: %s" % (e, h[1].text.strip(), h[1].select('a')[0].attrs['href'].split('playerid=')[1].split('&')[0]))

    def get_pitchers(self):
        url = f"https://www.fangraphs.com/leaders.aspx?pos=all&stats=pit&lg=all&qual=10&type=c,4,5,11,7,8,13,-1,36,37,40,43,44,48,51,-1,6,45,62,122,-1,59&season={self.season}&month=0&season1={self.season}&ind=0&team=0&rost=0&age=0&filter=&players=0&startdate=2019-01-01&enddate=2019-12-31&page=1_1100"

        rows = self.get_results(url)

        for row in rows:
            h = row.select('td')
            ls_dict = {}

            try:
                obj = models.Player.objects.get(fg_id=h[1].select('a')[0].attrs['href'].split('playerid=')[1].split('&')[0])
                obj.ls_g = int(h[6].text.strip())
                obj.ls_gs = int(h[7].text.strip())
                obj.ls_ip = Decimal(h[8].text.replace(' %', '').strip())
                obj.ls_k_9 = Decimal(h[9].text.replace(' %', '').strip())
                obj.ls_bb_9 = Decimal(h[10].text.replace(' %', '').strip())
                obj.ls_hr_9 = Decimal(h[11].text.replace(' %', '').strip())
                obj.ls_babip = Decimal(h[12].text.replace(' %', '').strip())
                obj.ls_lob_pct = Decimal(h[13].text.replace(' %', '').strip())
                obj.ls_gb_pct = Decimal(h[14].text.replace(' %', '').strip())
                obj.ls_hr_fb = Decimal(h[15].text.replace(' %', '').strip())
                obj.ls_era = Decimal(h[16].text.replace(' %', '').strip())
                obj.ls_fip = Decimal(h[17].text.replace(' %', '').strip())
                obj.ls_xfip = Decimal(h[18].text.replace(' %', '').strip())
                obj.ls_siera = Decimal(h[19].text.replace(' %', '').strip())
                obj.save()

            except Exception as e:
                print("%s\n  name: %s\n  fg_id: %s" % (e, h[1].text.strip(), h[1].select('a')[0].attrs['href'].split('playerid=')[1].split('&')[0]))
