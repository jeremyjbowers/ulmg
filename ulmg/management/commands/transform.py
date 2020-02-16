import csv
import json
import os

from bs4 import BeautifulSoup
from django.apps import apps
from django.db import connection
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError

from ulmg import models
from ulmg import utils


class Command(BaseCommand):

    def handle(self, *args, **options):
        with open('data/2020/jb_aa_pro.csv', 'r') as readfile:
            players = [dict(c) for c in csv.DictReader(readfile)]
            for p in players:
                # all the dudes without fg_ids
                if p['fg_id'] == '':
                    try:
                        obj = models.Player.objects.get(first_name=p['first'], last_name=p['last'])
                    except:
                        obj = models.Player()
                        obj.first_name = p['first']
                        obj.last_name = p['last']
                        obj.position = p['position']
                        obj.fg_id = p['fg_id']
                        obj.is_mlb = False
                        obj.is_amateur = False
                        obj.is_owned = False
                        obj.level = "B"
                        obj.save()
                        print(obj)

                # all the dudes who have fg_ids
                if p['fg_id'] != '':

                    try:
                        obj = models.Player.objects.get(fg_id=p['fg_id'])
                    except:
                        obj = models.Player()
                        obj.first_name = p['first']
                        obj.last_name = p['last']
                        obj.position = p['position']
                        obj.fg_id = p['fg_id']
                        obj.is_mlb = False
                        obj.is_amateur = False
                        obj.is_owned = False
                        obj.level = "B"
                        obj.save()
                        print(obj)