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

    def set_carded(self, *args, **optionals):
        print(".... setting carded status")
        for p in models.Player.objects.filter(ls_is_mlb=True, is_carded=False):
            p.is_carded=True
            p.save()

    def load_hitters(self, *args, **options):
        print(".... loading hitters")
        with open('data/2019/300_pa_hit.csv', 'r') as readfile:
            players = csv.DictReader(readfile)
            for row in [dict(z) for z in players]:
                try:
                    p = models.Player.objects.get(fg_id=row['playerid'])
                    p.cs_pa = row['PA']
                    p.save()
                except:
                    pass

    def load_pitchers(self, *args, **options):
        print(".... loading pitchers")
        with open('data/2019/40_ip_pit.csv', 'r') as readfile:
            players = csv.DictReader(readfile)
            for row in [dict(z) for z in players]:
                try:
                    p = models.Player.objects.get(fg_id=row['playerid'])
                    p.cs_st = row['GS']
                    p.cs_gp = row['G']
                    p.cs_ip = row['IP']
                    p.save()
                except:
                    pass

    def load_career_stats(self, *args, **options):
        self.load_hitters()
        self.load_pitchers()

    def set_levels(self):
        print("--------- STARTERS B > A ---------")
        for p in models.Player.objects.filter(level="B", position="P", cs_st__gte=21):
            p.level = "A"
            p.save()
            print(p)

        print("--------- RELIEVERS B > A ---------")
        for p in models.Player.objects.filter(level="B", position="P", cs_gp__gte=31, cs_st=0):
            p.level = "A"
            p.save()
            print(p)

        print("--------- SWINGMEN B > A ---------")
        for p in models.Player.objects.filter(level="B", position="P", cs_gp__gte=40, cs_st__gte=15):
            p.level = "A"
            p.save()
            print(p)

        print("--------- HITTERS B > A ---------")
        for p in models.Player.objects.filter(level="B", cs_pa__gte=300):
            p.level = "A"
            p.save()
            print(p)

        print("--------- STARTERS A > V ---------")
        for p in models.Player.objects.filter(level="A", position="P", cs_st__gte=126):
            p.level = "V"
            p.save()
            print(p)

        print("--------- RELIEVERS A > V ---------")
        for p in models.Player.objects.filter(level="A", position="P", cs_gp__gte=201, cs_st=0):
            p.level = "V"
            p.save()
            print(p)

        print("--------- SWINGMEN A > V ---------")
        for p in models.Player.objects.filter(level="A", position="P", cs_gp__gte=220, cs_st__gte=30):
            p.level = "V"
            p.save()
            print(p)

        print("--------- HITTERS A > V ---------")
        for p in models.Player.objects.filter(level="A", cs_pa__gte=2500):
            p.level = "V"
            p.save()
            print(p)

    def reset_rosters(self):
        print(".... resetting rosters")
        models.Player.objects.filter(is_mlb_roster=True).update(is_mlb_roster=False)
        models.Player.objects.filter(is_aaa_roster=True).update(is_aaa_roster=False)
        models.Player.objects.filter(is_1h_c=True).update(is_1h_c=False)
        models.Player.objects.filter(is_1h_p=True).update(is_1h_p=False)
        models.Player.objects.filter(is_1h_pos=True).update(is_1h_pos=False)
        models.Player.objects.filter(is_reserve=True).update(is_reserve=False)

    def handle(self, *args, **options):
        self.reset_rosters()
        self.set_carded()
        self.load_career_stats()
        self.set_levels()