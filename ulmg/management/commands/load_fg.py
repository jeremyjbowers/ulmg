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

    def get_prospect_rating(self, obj, p, idx):
        try:
            pr = models.ProspectRating.objects.get(player=obj)
            self.save_prospectrating(p, pr, idx)

        except models.ProspectRating.DoesNotExist:

            prs = utils.fuzzy_find_prospectrating(obj.name)
            print(prs)

            if len(prs) == 1:
                pr = prs[0]
                self.save_prospectrating(p, pr, idx)
                print(f'* {pr}')

            elif len(prs) == 0:
                    pr, created = models.ProspectRating.objects.get_or_create(
                        year=2021, player=obj, player_name=obj.name
                    )
                    self.save_prospectrating(p, pr, idx)
                    print(f'+ {pr}')


    def find_player(self, p):
        objs = utils.fuzzy_find_player(p["Name"])
        if len(objs) == 1:
            return objs[0]
        return None


    def save_prospectrating(self, p, pr, idx):
        if not pr.fg:
            if p['Top 100'] != "":
                pr.fg
            else:
                pr.fg = idx
 
        if not pr.rank_type:
            pr.rank_type = "board"
 
        pr.save()


    def save_player(self, obj, p):
        obj.position = utils.normalize_pos(p["Pos"])
        obj.is_mlb = False
        obj.is_prospect = True
        obj.level = "B"
        obj.notes = p["Report"].replace('<em>', '').replace('</em>', '')
        obj.fg_fv = utils.parse_fg_fv(p["FV"])
        obj.raw_age = int(p["Age"].split(".")[0])
        obj.fg_org_rank = utils.int_or_none(p['Org Rk'])

        try:
            obj.fg_eta = int(p["ETA"])
        except Exception as e:
            print(f"{e}\n{p}")

        obj.mlb_team = self.team_lookup[p['Org']]
        obj.mlb_team_abbr = p['Org']
        obj.save()


    def handle(self, *args, **options):
        with open("data/2021/fg_board.csv", "r") as readfile:
            players = [dict(c) for c in csv.DictReader(readfile)]
            for idx, p in enumerate(players):

                if p.get('playerId', None):
                    # have a playerid
                    try:
                        # try and lookup based on the playerid
                        obj = models.Player.objects.get(fg_id=p['playerId'])
                        self.save_player(obj, p)
                        self.get_prospect_rating(obj, p, idx)
                        continue

                    except models.Player.DoesNotExist:
                        # oh, a new player! try finding on name.
                        obj = self.find_player(p)

                        if obj:
                            # we found on the name, let's save
                            self.save_player(obj, p)
                            self.get_prospect_rating(obj, p, idx)
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
                        self.get_prospect_rating(obj, p, idx)
                        continue

                    else:
                        # either more than one was returned or none was returned.
                        # later, distinguish between these and prepare a "save new"
                        # or "disambiguate" loop.
                        print(f"No ID, not in DB!\n{p}")
                        continue

