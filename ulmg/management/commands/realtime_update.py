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
        self.season = settings.CURRENT_SEASON
        self.games = self.get_games()
        for game_id in self.games:
            self.load_game(game_id)

    def get_games(self):
        today = datetime.datetime.now(pytz.timezone('US/Eastern')).strftime("%m/%d/%Y")
        print(today)
        sched = [d['game_id'] for d in statsapi.schedule(start_date=today,end_date=today)]
        return sched

    def load_game(self, game_id):
        game = statsapi.boxscore_data(game_id)
        batters = []
        pitchers = []
        batters += [g for g in game['awayBatters'] if g['personId'] != 0]
        batters += [g for g in game['homeBatters'] if g['personId'] != 0]
        pitchers += [g for g in game['awayPitchers'] if g['personId'] != 0]
        pitchers += [g for g in game['homePitchers'] if g['personId'] != 0]

        for batter in batters:
            try:
                p = models.Player.objects.get(mlbam_id=batter['personId'])
                p.rt_ab = batter['ab']
                p.rt_r = batter['r']
                p.rt_h = batter['h']
                p.rt_doubles = batter['doubles']
                p.rt_triples = batter['triples']
                p.rt_hr = batter['hr']
                p.rt_rbi = batter['rbi']
                p.rt_sb = batter['sb']
                p.rt_bb = batter['bb']
                p.rt_k = batter['k']
                p.rt_lob = batter['lob']
                p.save()
            except:
                print(batter)