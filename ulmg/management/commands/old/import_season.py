import csv
import json
import os
from decimal import Decimal

from dateutil.parser import parse
from django.apps import apps
from django.db import connection
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings

from nameparser import HumanName

from ulmg import models, utils


class Command(BaseCommand):
    team_lookup = {}

    for team in settings.ROSTER_TEAM_IDS:
        team_lookup[team[1]] = team[2]

    def find_player(self, p):
        objs = utils.fuzzy_find_player(p["Name"])
        if len(objs) == 1:
            return objs[0]
        return None

    def save_player(self, obj, p):
        obj.position = utils.normalize_pos(p["Pos"])
        obj.is_mlb = True
        obj.is_carded = True
        obj.mlb_org = self.team_lookup[p["Team"]]
        obj.mlb_org_abbr = p["Team"]
        obj.save()

    def handle(self, *args, **options):
        with open("data/2021/fg_board.csv", "r") as readfile:
            players = [dict(c) for c in csv.DictReader(readfile)]
            for idx, p in enumerate(players):

                if p.get("playerId", None):
                    # have a playerid
                    try:
                        # try and lookup based on the playerid
                        obj = models.Player.objects.get(fg_id=p["playerId"])
                        self.save_player(obj, p)
                        continue

                    except models.Player.DoesNotExist:
                        # oh, a new player! try finding on name.
                        obj = self.find_player(p)

                        if obj:
                            # we found on the name, let's save
                            self.save_player(obj, p)
                            continue

                        else:
                            # either more than one was returned or none was returned.
                            # later, distinguish between these and prepare a "save new"
                            # or "disambiguate" loop.
                            print(f"Has ID, not in DB!\n{p}")
                            continue
                else:
                    # do not have a playerid, so find the player
                    obj = self.find_player(p)

                    if obj:
                        # we found on the name, let's save
                        self.save_player(obj, p)
                        continue

                    else:
                        # either more than one was returned or none was returned.
                        # later, distinguish between these and prepare a "save new"
                        # or "disambiguate" loop.
                        print(f"No ID, not in DB!\n{p}")
                        continue
