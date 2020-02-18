import csv
import json
import os
import time

from bs4 import BeautifulSoup
import requests
from django.apps import apps
from django.db import connection
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
import dateparser

from ulmg import models
from ulmg import utils


class Command(BaseCommand):

    def handle(self, *args, **options):
        def info_tranform(info):
            info = info.strip()
            if info == "med":
                return 1
            if info == "high":
                return 2
            return 0

        for path in ['data/2020/jb_aa_am.csv', 'data/2020/jb_aa_pro.csv']:
            with open(path, 'r') as readfile:
                players = [dict(c) for c in csv.DictReader(readfile)]
                for p in players:
                    obj = None
                    if p.get('fg_id', None):
                        if p['fg_id'] != '':
                            try:
                                obj = models.Player.objects.get(fg_id=p['fg_id'])
                            except:
                                print(p)
                    else:
                        name = "%s %s" % (p['first'], p['last'])
                        try:
                            obj = models.Player.objects.get(name=name)
                        except:
                            print(p)

                    if obj:
                        obj.b_interest = int(p['interest'])
                        obj.b_info = info_tranform(p['info'])
                        obj.b_important = True
                        obj.save()
