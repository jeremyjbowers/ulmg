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

"""
{"teamid": 8,
"loaddate": "2021-02-11T14:32:01",
"type": "off-rp",
"role": "AA",
"position": "RP",
"jnum": "",
"player": "Austin Schulfer",
"notes": "",
"handed": "R",
"age": "25.1",
"acquired": "Drafted 19th Rd '18",
"options": "Dec'21",
"servicetime": "",
"signyear": "2018",
"signround": "19",
"signpick": "574",
"retrodate": "",
"injurynotes": "",
"injurydate": "",
"mlbamid": 662165,
"age1": "25.1",
"jnum1": "",
"roster40": "N",
"bats": "R",
"throws": "R",
"position1": "RP",
"platoon": "",
"draftyear": "2018",
"draftround": "19",
"draftpick": "574",
"school": "Wisconsin-Milwaukee",
"originalteam": "MIN",
"servicetime1": "",
"projectedlevel": "",
"acquired1": "Drafted 19th Rd '18",
"country": "USA",
"acquiredcode": "HG",
"options1": "Dec'21",
"eta": "",
"isNRI": 0,
"mlbauto": 3007585,
"minorbamid": 662165,
"minormasterid": "sa3007585",
"statsid1": "sa1119513",
"mlbamid2": 662165,
"acquiredrecent": 0,
"oPlayerId": "sa3007585",
"dbTeam": "MIN",
"playerNameDisplay": "Austin Schulfer",
"playerNameRoute": "Austin Schulfer",
"mlevel": "A",
"team_abbrev": "MIN",
"team_name": "Minnesota Twins"}
"""


class Command(BaseCommand):
    season = None

    def handle(self, *args, **options):
        self.season = settings.CURRENT_SEASON

        ## fangraphs is apparently down right now?
        self.get_roster_info()
        self.get_new_players()
        self.parse_new_players()
        self.update_player_ids()
        self.parse_roster_info()

    def update_player_ids(self):
        print("UPDATE PLAYER IDS")
        """
        Catch players who have been given an MLBAM ID or an FG ID
        but who still have their minor league ID in our system.
        """
        teams = settings.ROSTER_TEAM_IDS
        for team_id, team_abbrev, team_name in teams:
            with open(f"data/rosters/{team_abbrev}_roster.json", "r") as readfile:
                roster = json.loads(readfile.read())
                for player in roster:

                    for id_type in ["minormasterid", "oPlayerId"]:
                        # we want to find those players whose fangraphs id changed
                        # from like sa12345 to 12345 because they got promoted last year.
                        # so, first: look up by one of the minor league ids.
                        # then, if that matches, update with the correct playerid.
                        if player.get(id_type, None) and player.get("playerid", None):
                            try:
                                p = models.Player.objects.get(fg_id=player[id_type])
                                p.fg_id = player["playerid"]

                                # while we got you here, update your mlb ids too.
                                for mlb_id in ["mlbamid", "minorbamid", "mlbamid2"]:
                                    if player.get(mlb_id, None):
                                        p.mlbam_id = player[mlb_id]
                                p.save()

                            except:
                                # if we can't find you, don't create anyone.
                                pass

    def parse_new_players(self):
        no_id_players = []

        print("PARSE NEW PLAYERS")
        with open("data/rosters/new_players.json", "r") as readfile:
            players = list(json.loads(readfile.read()))

        for player in players:
            fg_id = None

            # there are so many options for fg_ids
            if player.get("playerid", None):
                fg_id = player["playerid"]
            elif player.get("oPlayerId", None):
                fg_id = player["oPlayerId"]
            elif player.get("minormasterid", None):
                fg_id = player["minormasterid"]

            if not fg_id:
                no_id_players.append(player)

            else:
                # we've got a workable fangraphs id, let's find a player now.
                try:
                    p = models.Player.objects.get(fg_id=fg_id)

                    # we got a bingo! let's set the MLB id now because we know it.
                    for mlb_id in ["mlbamid", "minorbamid", "mlbamid2"]:
                        if player.get(mlb_id, None):
                            p.mlbam_id = player[mlb_id]

                    # save and get out.
                    p.save()

                except models.Player.DoesNotExist:

                    # Okay, we have failed the lookups, let's load this player now.
                    # we have a player id, so let's use it.

                    p = models.Player()
                    p.name = player["player"]

                    # there are so many options for fg_ids
                    p.fg_id = fg_id

                    # set a raw age, this won't matter if we have a birthdate.
                    p.raw_age = int(player["age"].split(".")[0])

                    # get an mlbam id if we can
                    for mlb_id in ["mlbamid", "minorbamid", "mlbamid2"]:
                        if player.get(mlb_id, None):
                            p.mlbam_id = player[mlb_id]

                    # get and set a position.
                    p.position = utils.normalize_pos(player.get("position", None))
                    p.level = "B"

                    if p.position:
                        # won't save if position is null
                        p.save()

        with open("data/rosters/no_id_players.json", "w") as writefile:
            writefile.write(json.dumps(no_id_players))

    def get_new_players(self):
        """
        "playerid"
        "oPlayerId"
        "minormasterid"

        "mlbamid"
        "minorbamid"
        "mlbamid2"
        """

        print("GET PLAYERS FROM ROSTERS")
        new_players = []
        more_than_one_players = []

        teams = settings.ROSTER_TEAM_IDS
        for team_id, team_abbrev, team_name in teams:

            with open(f"data/rosters/{team_abbrev}_roster.json", "r") as readfile:
                roster = json.loads(readfile.read())

                for player in roster:
                    player["team_abbrev"] = team_abbrev
                    player["team_name"] = team_name

                    # search by all combinations of fg id
                    for possible_id in ["playerid", "oPlayerId", "minormasterid"]:
                        if player.get(possible_id, None):
                            try:
                                p = models.Player.objects.get(fg_id=player[possible_id])

                            except models.Player.DoesNotExist:

                                # do a really tight fuzzy name search? (or dump to "possible")
                                p = utils.fuzzy_find_player(
                                    player["player"], score=0.75
                                )

                                if len(p) == 0:

                                    new_players.append(player)

                                if len(p) > 1:
                                    more_than_one_players.append(player)

                            except models.Player.MultipleObjectsReturned:
                                p = 1
                                more_than_one_players.append(player)

        with open("data/rosters/more_than_one_players.json", "w") as writefile:
            writefile.write(json.dumps(more_than_one_players))

        with open("data/rosters/new_players.json", "w") as writefile:
            writefile.write(json.dumps(new_players))

    def parse_roster_info(self):
        print("PARSE ROSTER INFO")

        """
        is_starter = models.BooleanField(default=False)
        is_bullpen = models.BooleanField(default=False)
        is_mlb40man = models.BooleanField(default=False)
        is_bench = models.BooleanField(default=False)
        is_player_pool = models.BooleanField(default=False)
        is_injured = models.BooleanField(default=False)
        injury_description = models.CharField(max_length=255, null=True)
        role = models.CharField(max_length=255, null=True)
        mlb_team = models.CharField(max_length=255, null=True)
        mlb_team_abbr = models.CharField(max_length=255, null=True)
        """

        models.Player.objects.update(
            is_starter=False,
            is_bench=False,
            is_player_pool=False,
            is_injured=False,
            is_mlb40man=False,
            is_bullpen=False,
            injury_description="",
            role="",
            mlb_team="",
            mlb_team_abbr="",
        )

        teams = settings.ROSTER_TEAM_IDS
        for team_id, team_abbrev, team_name in teams:
            with open(f"data/rosters/{team_abbrev}_roster.json", "r") as readfile:
                roster = json.loads(readfile.read())
                for player in roster:
                    p = None
                    try:
                        try:
                            p = models.Player.objects.get(fg_id=player["playerid"])
                        except:
                            try:
                                p = models.Player.objects.get(
                                    fg_id=player["minormasterid"]
                                )
                            except:
                                pass

                        if p:
                            p.role = player["role"]

                            if "pp" in player["type"]:
                                p.is_player_pool = True

                            if player["type"] == "mlb-tx-pp":
                                p.is_player_pool = True

                            if player["type"] == "mlb-tx-pt":
                                p.is_player_pool = True

                            if player["type"] == "mlb-bp":
                                p.is_bullpen = True

                            if player["type"] == "mlb-sp":
                                p.is_starter = True

                            if player["type"] == "mlb-bn":
                                p.is_bench = True

                            if player["type"] == "mlb-sl":
                                p.is_starter = True

                            if "il" in player["type"]:
                                p.is_injured = True

                            p.injury_description = player.get("injurynotes", None)
                            p.mlbam_id = player.get("mlbamid1", None)
                            p.mlb_team = team_name
                            p.mlb_team_abbr = team_abbrev

                            if player["roster40"] == "Y":
                                p.is_mlb40man = True

                            # set a raw age, this won't matter if we have a birthdate.
                            p.raw_age = int(player["age"].split(".")[0])

                            p.save()

                    except Exception as e:
                        print(f"error loading {player['player']}: {e}")

    def get_roster_info(self):
        print("GET ROSTER INFO")
        teams = settings.ROSTER_TEAM_IDS
        for team_id, team_abbrev, team_name in teams:
            url = f"https://cdn.fangraphs.com/api/depth-charts/roster?teamid={team_id}"
            roster = requests.get(url).json()
            with open(f"data/rosters/{team_abbrev}_roster.json", "w") as writefile:
                writefile.write(json.dumps(roster))
