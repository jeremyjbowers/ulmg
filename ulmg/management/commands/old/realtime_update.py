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
import statsapi

import datetime
import pytz


class Command(BaseCommand):
    season = None
    games = []

    def handle(self, *args, **options):
        self.games = self.get_games()
        for game_id in self.games:
            self.load_game(game_id)

    def wipe_realtime_stats(self):
        models.Player.objects.update(
            rt_ab=None,
            rt_r=None,
            rt_h=None,
            rt_doubles=None,
            rt_triples=None,
            rt_hr=None,
            rt_rbi=None,
            rt_sb=None,
            rt_bb=None,
            rt_k=None,
            rt_ip=None,
            rt_ph=None,
            rt_pr=None,
            rt_er=None,
            rt_pbb=None,
            rt_pk=None,
            rt_phr=None,
            rt_p=None,
            rt_s=None,
        )

    def get_games(self):
        pacific = pytz.timezone("US/Pacific")
        now = datetime.datetime.now()
        now = pacific.localize(now)
        start_time = datetime.datetime(now.year, now.month, now.day, 8, 0, 0, 0)
        start_time = pacific.localize(start_time)
        if now >= start_time:
            # wipe old data if we're past 8am PST
            self.wipe_realtime_stats()

        today = now.strftime("%m/%d/%Y")
        print(now)
        print(start_time)
        print(f"Loading realtime data for {today}")
        sched = [
            d["game_id"] for d in statsapi.schedule(start_date=today, end_date=today)
        ]
        return sched

    def load_game(self, game_id):
        game = statsapi.boxscore_data(game_id)
        batters = []
        pitchers = []
        batters += [g for g in game["awayBatters"] if g["personId"] != 0]
        batters += [g for g in game["homeBatters"] if g["personId"] != 0]
        pitchers += [g for g in game["awayPitchers"] if g["personId"] != 0]
        pitchers += [g for g in game["homePitchers"] if g["personId"] != 0]

        for batter in batters:
            try:
                p = models.Player.objects.get(mlbam_id=batter["personId"])
                p.rt_ab = batter["ab"]
                p.rt_r = batter["r"]
                p.rt_h = batter["h"]
                p.rt_doubles = batter["doubles"]
                p.rt_triples = batter["triples"]
                p.rt_hr = batter["hr"]
                p.rt_rbi = batter["rbi"]
                p.rt_sb = batter["sb"]
                p.rt_bb = batter["bb"]
                p.rt_k = batter["k"]
                p.rt_lob = batter["lob"]
                p.save()
            except Exception as e:
                print(
                    f"{e} {batter['position']} | {batter['personId']} | {batter['name']}"
                )

        for pitcher in pitchers:
            try:
                p = models.Player.objects.get(mlbam_id=pitcher["personId"])
                p.rt_ip = pitcher["ip"]
                p.rt_ph = pitcher["h"]
                p.rt_pr = pitcher["r"]
                p.rt_er = pitcher["er"]
                p.rt_pbb = pitcher["bb"]
                p.rt_pk = pitcher["k"]
                p.rt_phr = pitcher["hr"]
                p.rt_p = pitcher["p"]
                p.rt_s = pitcher["s"]
                p.save()
            except Exception as e:
                print(f"{e} P | {pitcher['personId']} | {pitcher['name']}")
