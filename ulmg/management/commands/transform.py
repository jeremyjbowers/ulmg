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
        def write_csv(path, payload):
            with open(path, 'w') as csvfile:
                fieldnames = list(payload[0].keys())
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                for p in payload:
                    writer.writerow(p)

        def normalize_pos(pos):
            if pos.upper() in ["1B", "2B", "3B", "SS"]:
                pos = "IF"
            if pos.upper() in ["RF", "CF", "LF"]:
                pos = "OF"
            if "P" in pos.upper():
                pos = "P"
            return pos

        for pick in models.DraftPick.objects.filter(year="2018"):
            if pick.player_name:
                player = models.Player.objects.filter(name=pick.player_name)
                if len(player) == 1:
                    pick.player = player[0]
                    pick.save()
                    print(pick.player.name)