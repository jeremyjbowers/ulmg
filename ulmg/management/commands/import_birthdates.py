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
        for obj in models.Player.objects.filter(
            fg_id__isnull=False, birthdate__isnull=True
        ).exclude(fg_id=""):
            r = requests.get(obj.fg_url)
            soup = BeautifulSoup(r.text, "lxml")
            b1 = soup.select("tr.player-info__bio-birthdate td")[0].contents
            b2 = b1[0].split(" (")[0].strip()
            birthdate = dateparser.parse(b2)
            obj.birthdate = birthdate.date()
            obj.save()
            print(obj)
            time.sleep(1)
