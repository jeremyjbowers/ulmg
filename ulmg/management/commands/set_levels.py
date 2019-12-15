import csv
import json
import os
from decimal import *

from bs4 import BeautifulSoup
from django.apps import apps
from django.db import connection
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError

from ulmg import models


'''
# CAREER STATS (for level)
cs_pa = models.IntegerField(blank=True, null=True)
cs_gp = models.IntegerField(blank=True, null=True)
cs_st = models.IntegerField(blank=True, null=True)
cs_ip = models.DecimalField(max_digits=4, decimal_places=1, blank=True, null=True)
'''
class Command(BaseCommand):
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


    def handle(self, *args, **options):
        self.load_career_stats()
        self.set_levels()