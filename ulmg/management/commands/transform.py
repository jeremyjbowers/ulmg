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
        with open('data/2020/jb_aa_am.csv', 'r') as readfile:
            players = [dict(c) for c in csv.DictReader(readfile)]
            for p in players:
                name = "%s %s" % (p['first'], p['last'])
                try:
                    obj = models.Player.objects.get(name=name)
                except:
                    obj = models.Player()
                    obj.first_name = p['first']
                    obj.last_name = p['last']
                    obj.position = p['pos']
                    obj.is_mlb = False
                    obj.is_amateur = True
                    obj.is_owned = False
                    obj.level = "B"
                    obj.notes = p['notes']
                    obj.save()
                    print(obj)

