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
        for pick in models.DraftPick.objects.filter(year="2018"):
            if pick.player_name:
                player = models.Player.objects.filter(name=pick.player_name)
                if len(player) == 1:
                    pick.player = player[0]
                    pick.save()
                    print(pick.player.name)