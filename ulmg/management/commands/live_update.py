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
        self.get_mlbam()
        self.get_minors()

    def get_fg_results(self, url):
        r = requests.get(url)
        soup = BeautifulSoup(r.text, 'lxml')
        return soup.select('#LeaderBoard1_dg1_ctl00 tbody tr')

    def get_minors(self):
        headers = {
            "accept": "application/json"
        }

        players = {
            'bat': [],
            'pit': []
        }

        for k,v in players.items():
            url = f"https://www.fangraphs.com/api/leaders/minor-league/data?pos=all&lg=2,4,5,6,7,8,9,10,11,14,12,13,15,17,18,30,32,33&stats={k}&qual=5&type=0&team=&season={self.season}&seasonEnd={self.season}&org=&ind=0&splitTeam=false"
            r = requests.get(url)
            players[k] += r.json()

        for k,v in players.items():
            for player in v:
                fg_id = player['Name'].split('?playerid=')[1].split('&')[0].strip()
                name = player['Name'].split('>')[1].split('<')[0].strip()
                p = models.Player.objects.filter(fg_id=fg_id)
                count = models.Player.objects.filter(fg_id=fg_id, ls_is_mlb=False).count()

                if count == 1:
                    obj = p[0]
                    
                    try:
                        if k == "bat":
                            obj.ls_hr = int(player['HR'])
                            obj.ls_sb = int(player['SB'])
                            obj.ls_runs = int(player['R'])
                            obj.ls_rbi = int(player['RBI'])
                            obj.ls_avg = Decimal(player['AVG'])
                            obj.ls_obp = Decimal(player['OBP'])
                            obj.ls_slg = Decimal(player['SLG'])
                            obj.ls_babip = Decimal(player['BABIP'])
                            obj.ls_wrc_plus = int(player['wRC+'])
                            obj.ls_plate_appearances = int(player['PA'])
                            obj.ls_iso = Decimal(player['ISO'])
                            obj.ls_k_pct = Decimal(round(float(player['K%']) * 100.0, 1))
                            obj.ls_bb_pct = Decimal(round(float(player['BB%']) * 100.0, 1))
                            obj.ls_woba = Decimal(player['wOBA'])
                            obj.save()
                        
                        if k == "pit":
                            obj.ls_g = int(player['G'])
                            obj.ls_gs = int(player['GS'])
                            obj.ls_ip = Decimal(round(float(player['IP']), 1))
                            obj.ls_k_9 = Decimal(round(float(player['K/9']), 2))
                            obj.ls_bb_9 = Decimal(round(float(player['BB/9']), 2))
                            obj.ls_hr_9 = Decimal(round(float(player['HR/9']), 2))
                            obj.ls_lob_pct = Decimal(round(float(player['LOB%']) * 100.0, 1))
                            obj.ls_gb_pct = Decimal(round(float(player['GB%']) * 100.0, 1))
                            obj.ls_hr_fb = Decimal(round(float(player['HR/FB']), 1))
                            obj.ls_era = Decimal(round(float(player['ERA']), 2))
                            obj.ls_fip = Decimal(round(float(player['FIP']), 2))
                            obj.ls_xfip = Decimal(round(float(player['xFIP']), 2))
                            obj.save()
                    except:
                        print(player)

    def get_mlbam(self):
        curl_cmd = f'curl -o /tmp/mlbam.csv "https://baseballsavant.mlb.com/expected_statistics?type=batter&year={self.season}&position=&team=&min=5&csv=true"'
        os.system(curl_cmd)
        with open('/tmp/mlbam.csv', 'r') as readfile:
            players = [dict(c) for c in csv.DictReader(readfile)]
            for p in players:
                try:
                    obj = models.Player.objects.get(mlbam_id=p['player_id'])
                    obj.ls_is_mlb = True
                    obj.ls_xavg = Decimal(p['est_ba'])
                    obj.ls_xwoba = Decimal(p['est_woba'])
                    obj.ls_xslg = Decimal(p['est_slg'])
                    obj.ls_xwoba_diff = Decimal(p['est_woba_minus_woba_diff'])
                    obj.ls_xslg_diff = Decimal(p['est_slg_minus_slg_diff'])
                    obj.ls_xavg_diff = Decimal(p['est_ba_minus_ba_diff'])
                    obj.save()

                except:
                    print(p)


    def get_hitters(self):
        url = f"https://www.fangraphs.com/leaders.aspx?pos=all&stats=bat&lg=all&qual=5&type=8&season={self.season}&month=0&season1={self.season}&ind=0&team=0&rost=0&age=0&filter=&players=0&startdate=&enddate=&page=1_1500"
        print(url)
        rows = self.get_fg_results(url)

        for row in rows:
            h = row.select('td')
            ls_dict = {}

            try:
                obj = models.Player.objects.get(fg_id=h[1].select('a')[0].attrs['href'].split('playerid=')[1].split('&')[0])
                obj.ls_is_mlb = True
                obj.ls_plate_appearances = int(h[4].text.strip())
                obj.ls_hr = int(h[5].text.strip())
                obj.ls_runs = int(h[6].text.strip())
                obj.ls_rbi = int(h[7].text.strip())
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
                print("h,%s,%s" % (h[1].text.strip(), h[1].select('a')[0].attrs['href'].split('playerid=')[1].split('&')[0]))

    def get_pitchers(self):
        url = f"https://www.fangraphs.com/leaders.aspx?pos=all&stats=pit&lg=all&qual=5&type=c,4,5,11,7,8,13,-1,36,37,40,43,44,48,51,-1,6,45,62,122,-1,59&season={self.season}&month=0&season1={self.season}&ind=0&team=0&rost=0&age=0&filter=&players=0&startdate=2019-01-01&enddate=2019-12-31&page=1_1100"

        rows = self.get_fg_results(url)

        for row in rows:
            h = row.select('td')
            ls_dict = {}

            try:
                obj = models.Player.objects.get(fg_id=h[1].select('a')[0].attrs['href'].split('playerid=')[1].split('&')[0])
                obj.ls_is_mlb = True
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
                print("p,%s,%s" % (h[1].text.strip(), h[1].select('a')[0].attrs['href'].split('playerid=')[1].split('&')[0]))
