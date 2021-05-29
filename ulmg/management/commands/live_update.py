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


class Command(BaseCommand):
    season = None

    def handle(self, *args, **options):
        self.season = settings.CURRENT_SEASON
        self.reset_players()

        # FG VIA ROSTER RESOURCE
        self.get_roster_info()
        self.update_player_ids()
        self.parse_roster_info()

        # FG CSVs
        self.get_hitters()
        self.get_pitchers()

        # FG weird API URL
        self.get_minors()

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
                "ls_runs",
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
            set_hitters(team)
            set_pitchers(team)
            team.save()

    def update_player_ids(self):
        print("UPDATE PLAYER IDS")
        teams = settings.ROSTER_TEAM_IDS
        for team_id, team_abbrev, team_name in teams:
            with open(f"data/rosters/{team_abbrev}_roster.json", "r") as readfile:
                roster = json.loads(readfile.read())
                for player in roster:
                    if player.get("minormasterid", None) and player.get(
                        "playerid", None
                    ):
                        try:
                            p = models.Player.objects.get(fg_id=player["minormasterid"])
                            p.fg_id = player["playerid"]
                            p.save()
                        except:
                            pass

    def parse_roster_info(self):
        print("PARSE ROSTER INFO")

        """
        is_starter = models.BooleanField(default=False)
        is_bullpen = models.BooleanField(default=False)
        is_mlb40man = models.BooleanField(default=False)
        is_bench = models.BooleanField(default=False)
        is_player_pool = models.BooleanField(default=False)
        is_injured = models.BooleanField(default=False)
        injury_description = models.CharField(max_length=255, null=True)
        role = models.CharField(max_length=255, null=True)
        mlb_team = models.CharField(max_length=255, null=True)
        mlb_team_abbr = models.CharField(max_length=255, null=True)
        """

        models.Player.objects.update(
            is_starter=False,
            is_bench=False,
            is_player_pool=False,
            is_injured=False,
            is_mlb40man=False,
            is_bullpen=False,
            injury_description="",
            role="",
            mlb_team="",
            mlb_team_abbr="",
        )

        teams = settings.ROSTER_TEAM_IDS
        for team_id, team_abbrev, team_name in teams:
            with open(f"data/rosters/{team_abbrev}_roster.json", "r") as readfile:
                roster = json.loads(readfile.read())
                for player in roster:
                    p = None
                    try:
                        try:
                            p = models.Player.objects.get(fg_id=player["playerid"])
                        except:
                            try:
                                p = models.Player.objects.get(
                                    fg_id=player["minormasterid"]
                                )
                            except:
                                pass

                        if p:
                            if player.get('mlevel', None):
                                p.role = player["mlevel"]
                            elif player.get('role', None):
                                if player['role'] != '':
                                    p.role = player["role"]

                            if p.role == "MLB":
                                p.ls_is_mlb = True
                                p.is_mlb = True

                            if "pp" in player["type"]:
                                p.is_player_pool = True

                            if player["type"] == "mlb-tx-pp":
                                p.is_player_pool = True

                            if player["type"] == "mlb-tx-pt":
                                p.is_player_pool = True

                            if player["type"] == "mlb-bp":
                                p.is_bullpen = True

                            if player["type"] == "mlb-sp":
                                p.is_starter = True

                            if player["type"] == "mlb-bn":
                                p.is_bench = True

                            if player["type"] == "mlb-sl":
                                p.is_starter = True

                            if "il" in player["type"]:
                                p.is_injured = True

                            p.injury_description = player.get("injurynotes", None)
                            p.mlbam_id = player.get("mlbamid1", None)
                            p.mlb_team = team_name
                            p.mlb_team_abbr = team_abbrev

                            if player["roster40"] == "Y":
                                p.is_mlb40man = True

                            p.save()

                    except Exception as e:
                        print(f"error loading {player['player']}: {e}")

    def get_roster_info(self):
        print("GET ROSTER INFO")
        teams = settings.ROSTER_TEAM_IDS
        for team_id, team_abbrev, team_name in teams:
            url = f"https://cdn.fangraphs.com/api/depth-charts/roster?teamid={team_id}"
            roster = requests.get(url).json()
            with open(f"data/rosters/{team_abbrev}_roster.json", "w") as writefile:
                writefile.write(json.dumps(roster))

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

    def get_fg_results(self, url):
        r = requests.get(url)
        soup = BeautifulSoup(r.text, "lxml")
        return soup.select("#LeaderBoard1_dg1_ctl00 tbody tr")

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
                            obj.ls_hits = int(player['H'])
                            obj.ls_2b = int(player['2B'])
                            obj.ls_3b = int(player['3B'])
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
                            obj.ls_k = int(player['SO'])
                            obj.ls_bb = int(player['BB'])
                            obj.ls_ha = int(player['H'])
                            obj.ls_hra = int(player['HR'])
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


    def get_hitters(self):
        print("FG HITTERS")
        url = f"https://www.fangraphs.com/leaders.aspx?pos=all&stats=bat&lg=all&qual=0&type=c,6,-1,312,305,309,306,307,308,310,311,-1,23,315,-1,38,316,-1,50,317,7,8,9,10,11,12,13,14,21,23,34,35,37,38,39,40,41,50,52,57,58,61,62&season={self.season}&month=0&season1={self.season}&ind=0&team=0&rost=0&age=0&filter=&players=0&startdate={self.season}-01-01&enddate={self.season}-12-31&sort=3,d&page=1_5000"
        rows = self.get_fg_results(url)

        """
        0: number, 1: name, 2: team, 3: pa, 4: events, 5: ev, 6: max_ev, 7: la, 8: barrels, 9: barrel_pct, 10: hard_hit, 11: hard_hit_pct, 12: avg, 13: xavg, 14: slg, 15: xslg, 16: woba, 17: xwoba, 18: h, 19: 1b, 20: 2b, 21: 3b, 22: hr, 23: r, 24: rbi, 25: bb, 26: sb, 27: avg, 28: bb%, 29: k%, 30: obp, 31: slg, 32: ops, 33: iso, 34: babip, 35: woba, 36: wrc, 37: rar, 38: war, 39: wrc+, 40: wpa
        """
        for row in rows:
            h = row.select("td")
            ls_dict = {}

            try:
                obj = models.Player.objects.get(
                    fg_id=h[1]
                    .select("a")[0]
                    .attrs["href"]
                    .split("playerid=")[1]
                    .split("&")[0]
                )
                if obj.position != "P":
                    obj.ls_hits = int(h[18].text)
                    obj.ls_2b = int(h[20].text)
                    obj.ls_3b = int(h[21].text)
                    obj.ls_hr = int(h[22].text)
                    obj.ls_sb = int(h[26].text)
                    obj.ls_runs = int(h[23].text)
                    obj.ls_rbi = int(h[24].text)
                    obj.ls_avg = Decimal(h[12].text)
                    obj.ls_xavg = Decimal(h[13].text)
                    obj.ls_obp = Decimal(h[30].text)
                    obj.ls_slg = Decimal(h[14].text)
                    obj.ls_xslg = Decimal(h[15].text)
                    obj.ls_babip = Decimal(h[34].text)
                    obj.ls_wrc_plus = int(h[39].text)
                    obj.ls_plate_appearances = int(h[3].text)
                    obj.ls_iso = Decimal(h[33].text)
                    obj.ls_k_pct = Decimal(round(float(h[29].text.replace('%', '')), 1))
                    obj.ls_bb_pct = Decimal(round(float(h[28].text.replace('%', '')), 1))
                    obj.ls_woba = Decimal(h[16].text)
                    obj.ls_xwoba = Decimal(h[17].text)
                    obj.save()

            except Exception as e:
                print(round(float(h[29].text.replace('%', '')), 1))
                print(round(float(h[28].text.replace('%', '')), 1))
                print(
                    f"h: {h[1].select('a')[0].attrs['href'].split('playerid=')[1].split('&')[0]}\t{h[1].text.strip()}\t{e}"
                )


    def get_pitchers(self):
        print("FG PITCHERS")
        url = f"https://www.fangraphs.com/leaders.aspx?pos=all&stats=pit&lg=all&qual=2&type=c,4,5,11,7,8,13,-1,24,19,15,18,36,37,40,43,44,48,51,-1,240,-1,6,332,45,62,122,-1,59&season={self.season}&month=0&season1={self.season}&ind=0&team=0&rost=0&age=0&filter=&players=0&startdate={self.season}-01-01&enddate={self.season}-12-31&sort=8,d&page=1_5000"

        rows = self.get_fg_results(url)

        for row in rows:
            h = row.select("td")
            ls_dict = {}

            try:
                obj = models.Player.objects.get(
                    fg_id=h[1]
                    .select("a")[0]
                    .attrs["href"]
                    .split("playerid=")[1]
                    .split("&")[0]
                )
                obj.ls_g = int(h[6].text)
                obj.ls_gs = int(h[7].text)
                obj.ls_k = int(h[9].text)
                obj.ls_bb = int(h[10].text)
                obj.ls_ha = int(h[11].text)
                obj.ls_hra = int(h[12].text)
                obj.ls_ip = Decimal(round(float(h[8].text.replace('%', '')), 1))
                obj.ls_k_9 = Decimal(round(float(h[13].text.replace('%', '')), 2))
                obj.ls_bb_9 = Decimal(round(float(h[14].text.replace('%', '')), 2))
                obj.ls_hr_9 = Decimal(round(float(h[15].text.replace('%', '')), 2))
                obj.ls_lob_pct = Decimal(round(float(h[17].text.replace('%', '')), 1))
                obj.ls_gb_pct = Decimal(round(float(h[18].text.replace('%', '')), 1))
                obj.ls_hr_fb = Decimal(round(float(h[19].text.replace('%', '')), 1))
                obj.ls_era = Decimal(round(float(h[21].text.replace('%', '')), 2))
                obj.ls_fip = Decimal(round(float(h[23].text.replace('%', '')), 2))
                obj.ls_xfip = Decimal(round(float(h[24].text.replace('%', '')), 2))
                obj.ls_siera = Decimal(round(float(h[25].text.replace('%', '')), 2))
                obj.save()

                obj.save()

            except Exception as e:
                print(
                    f"p: {h[1].select('a')[0].attrs['href'].split('playerid=')[1].split('&')[0]}\t{h[1].text.strip()}\t{e}"
                )
