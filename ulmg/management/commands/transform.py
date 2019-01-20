import csv
import json
import os

from bs4 import BeautifulSoup
from django.apps import apps
from django.db import connection
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError

from ulmg import models


class Command(BaseCommand):

    def handle(self, *args, **options):

        def normalize_pos(pos):
            if pos.upper() in ["1B", "2B", "3B", "SS"]:
                pos = "IF"
            if pos.upper() in ["RF", "CF", "LF"]:
                pos = "OF"
            if "P" in pos.upper():
                pos = "P"
            return pos

        with open('data/j2/2018-ba-j2.json', 'r') as readfile:
            players = json.loads(readfile.read())

        with open('data/j2/2018-ba-j2.csv', 'w') as writefile:
            fieldnames = list(players[0].keys())
            writer = csv.DictWriter(writefile, fieldnames=fieldnames)
            writer.writeheader()
            for p in players:
                writer.writerow(p)            