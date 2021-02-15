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
        with open("data/2021/fg_2021_draft_board.csv", "r") as readfile:
            players = [dict(c) for c in csv.DictReader(readfile)]
            for p in players:
                obj = None
                objs = utils.fuzzy_find_player(p['Name'])
                if len(objs) == 1:
                    obj = objs[0]
                    obj.notes = p['Report']
                    obj.fg_fv = utils.parse_fg_fv(p['FV'])
                    obj.raw_age = int(p['Age'].split('.')[0])
                    obj.class_year = int(p['Class'])

                    prs = utils.fuzzy_find_prospectrating(p['Name'])
                    if len(prs) == 1:
                        pr = prs[0]
                        if not pr.player:
                            pr.player = obj
                            pr.save()
                            print(f"* +pr {obj}")
                        else:
                            print(f"* {obj}")
                
                else:
                    if len(objs) == 0:
                        obj = models.Player()
                        obj = models.Player()
                        name = HumanName(p["Name"])
                        obj.name = p["Name"]
                        obj.first_name = name.first
                        if name.middle:
                            obj.last_name = "%s %s" % (name.middle, name.last)
                        else:
                            obj.last_name = name.last
                        obj.position = utils.normalize_pos(p["Pos"])
                        obj.is_mlb = False
                        obj.is_amateur = True
                        obj.is_owned = False
                        obj.level = "B"
                        obj.notes = p["Report"]
                        obj.fg_fv = utils.parse_fg_fv(p['FV'])
                        obj.raw_age = int(p['Age'].split('.')[0])
                        obj.class_year = int(p['Class']) 
                        print(f"+ {obj}")

                if obj:
                    obj.save()
