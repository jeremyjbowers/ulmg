import csv
import json
import os
from decimal import Decimal

from dateutil.parser import parse
from django.apps import apps
from django.db import connection
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from nameparser import HumanName

from ulmg import models
from ulmg import utils


class Command(BaseCommand):

    def handle(self, *args, **options):
        with open('data/2020/fg_2019_board.csv', 'r') as readfile:
            players = [dict(c) for c in csv.DictReader(readfile)]
            for p in players:
                if p['playerId'] != '':
                    try:
                        obj = models.Player.objects.get(fg_id=p['playerId'])
                        obj.notes = p['Report']
                        obj.save()
                    except:
                        obj = models.Player()
                        name = HumanName(p['Name'])
                        obj.name = p['Name']
                        obj.first_name = name.first
                        if name.middle:
                            obj.last_name = "%s %s" % (name.middle, name.last)
                        else:
                            obj.last_name = name.last
                        obj.position = utils.normalize_pos(p['Pos'])
                        obj.fg_id = p['playerId']
                        obj.is_mlb = False
                        obj.is_amateur = False
                        obj.is_owned = False
                        obj.level = "B"
                        obj.notes = p['Report']
                        obj.save()
                        print(obj)