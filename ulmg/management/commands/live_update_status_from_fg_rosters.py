import csv
import json
import os
from decimal import Decimal

from bs4 import BeautifulSoup
from dateutil.parser import parse
from django.apps import apps
from django.db import connection
from django.db.models import Avg, Sum, Count
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
import requests

from ulmg import models, utils


class Command(BaseCommand):

    def handle(self, *args, **options):
        teams = settings.ROSTER_TEAM_IDS

        models.Player.objects.all().update(role_type=None, is_injured=False, role=None, is_starter=False, is_bench=False, injury_description=None, is_mlb40man=False)

        for team_id, team_abbrev, team_name in teams:
            with open(f"data/rosters/{team_abbrev}_roster.json", "r") as readfile:
                roster = json.loads(readfile.read())

                for player in roster:
                    obj = None
                    fg_id = None
                    mlbam_id = None

                    # mlbam has a lot of different ID fields
                    # let's try to get one
                    if player.get('mlbamid'):
                        mlbam_id = str(player['mlbamid']).strip()
                        if mlbam_id.strip() == "":
                            mlbam_id = None

                    if player.get('mlbamid1') and not mlbam_id:
                        mlbam_id = str(player['mlbamid1']).strip()
                        if mlbam_id.strip() == "":
                            mlbam_id = None

                    if player.get('mlbamid2') and not mlbam_id:
                        mlbam_id = str(player['mlbamid2']).strip()
                        if mlbam_id.strip() == "":
                            mlbam_id = None

                    if player.get('minorbamid') and not mlbam_id:
                        mlbam_id = str(player['minorbamid']).strip()
                        if mlbam_id.strip() == "":
                            mlbam_id = None

                    # fg has a lot of different ID fields
                    # let's try and get one
                    if player.get("playerid"):
                        fg_id = str(player["playerid"]).strip()
                        if fg_id.strip() == "":
                            fg_id = None

                    if player.get("playerid1") and not fg_id:
                        fg_id = str(player["playerid1"]).strip()
                        if fg_id.strip() == "":
                            fg_id = None

                    if player.get("playerid2") and not fg_id:
                        fg_id = str(player["playerid2"]).strip()
                        if fg_id.strip() == "":
                            fg_id = None

                    if player.get("oPlayerId") and not fg_id:
                        fg_id = str(player["oPlayerId"]).strip()
                        if fg_id.strip() == "":
                            fg_id = None

                    if fg_id:
                        try:
                            obj = models.Player.objects.get(fg_id=fg_id)
                        except:
                            pass

                    if mlbam_id and not obj:
                        try:
                            obj = models.Player.objects.get(mlbam_id=mlbam_id)
                        except:
                            pass

                    if not obj:
                        # time to create a new player
                        """
                        {'teamid': 30, 'loaddate': '2025-03-29T00:35:30', 'type': 'off-sp', 'role': 'A', 'position': 'SP', 'jnum': '', 'player': 'Cade Vernon', 'notes': '', 'handed': 'R', 'age': '23.2', 'acquired': "Drafted 10th Rd '24", 'options': "Dec'27", 'servicetime': '', 'signyear': '2024', 'signround': '10', 'signpick': '298', 'retrodate': '', 'injurynotes': '', 'injurydate': '', 'mlbamid': 827293, 'age1': '23.2', 'jnum1': '', 'roster40': 'N', 'bats': 'S', 'throws': 'R', 'position1': 'SP', 'platoon': '', 'draftyear': '2024', 'draftround': '10', 'draftpick': '298', 'school': 'Murray State', 'originalteam': 'SF', 'servicetime1': '', 'projectedlevel': '#N/A', 'acquired1': "Drafted 10th Rd '24", 'country': 'USA', 'acquiredcode': 'HG', 'options1': "Dec'27", 'eta': '', 'isNRI': 0, 'isCV19': 0, 'isAFL': 0, 'mlbauto': 3044462, 'minorbamid': 827293, 'minormasterid': 'sa3044462', 'csid': 'vernoca42', 'mlbamid2': 827293, 'acquiredrecent': 0, 'oPlayerId': 'sa3044462', 'dbTeam': 'SFG', 'playerNameDisplay': 'Cade Vernon', 'playerNameRoute': 'Cade Vernon'}
                        """
                        obj = models.Player()
                        obj.level = "B"
                        obj.name = player['player']
                        obj.position = utils.normalize_pos(player['position'])
                        obj.mlb_org = team_abbrev
                        obj.fg_id = fg_id
                        obj.mlbam_id = mlbam_id
                        obj.raw_age = player['age'].split('.')[0]
                        print(f"+++ {obj}")

                    obj.is_injured = False
                    obj.role = None
                    obj.is_starter = False
                    obj.is_bench = False
                    obj.injury_description = None
                    obj.is_mlb40man = False
                    obj.role_type = None

                    if player.get("mlevel", None):
                        obj.role = player["mlevel"]
                    
                    elif player.get("role", None):
                        if player["role"].strip() != "":
                            obj.role = player["role"]

                    if obj.role == "MLB":
                        obj.is_mlb40man = True

                    if player.get('type', None):
                        if player["type"] == "mlb-bp":
                            obj.is_bullpen = True

                        if player["type"] == "mlb-sp":
                            obj.is_starter = True

                        if player["type"] == "mlb-bn":
                            obj.is_bench = True

                        if player["type"] == "mlb-sl":
                            obj.is_starter = True

                        obj.role_type = player['type']

                        # if "il" in player["type"]:
                        #     obj.is_injured = True

                        # if "sp" in player['type']:
                        #     obj.role_type = "SP"

                        # if "rp" in player['type']:
                        #     obj.role_type = "RP"

                        # if "bp" in player['type']:
                        #     obj.role_type = "RP"

                        # if "pp" in player['type']:
                        #     obj.role_type = "PP"

                        # if "bn" in player['type']:
                        #     obj.role_type = "BN"

                        # if "il" in player['type']:
                        #     obj.role_type = "IL"

                    obj.injury_description = player.get("injurynotes", None)

                    if player.get('roster40', None):
                        if player["roster40"] == "Y":
                            obj.is_mlb40man = True

                    obj.save()