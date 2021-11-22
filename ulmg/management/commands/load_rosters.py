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
{
  "teamid": 1,
  "loaddate": "2021-11-21T17:15:39",
  "type": "mlb-sp",
  "role": "SP6",
  "position": "SP",
  "jnum": "48",
  "player": "Reid Detmers",
  "notes": "",
  "handed": "L",
  "age": "22.4",
  "acquired": "Drafted 1st Rd (10) '20",
  "options": "3",
  "servicetime": "0.055",
  "signyear": "2020",
  "signround": "1",
  "signpick": "10",
  "retrodate": "",
  "injurynotes": "",
  "injurydate": "",
  "mlbamid": 672282,
  "age1": "22.4",
  "jnum1": "48",
  "roster40": "Y",
  "bats": "L",
  "throws": "L",
  "position1": "SP",
  "platoon": "",
  "draftyear": "2020",
  "draftround": "1",
  "draftpick": "10",
  "school": "Louisville",
  "originalteam": "LAA",
  "servicetime1": "0.055",
  "projectedlevel": "",
  "acquired1": "Drafted 1st Rd (10) '20",
  "country": "USA",
  "acquiredcode": "HG",
  "options1": "3",
  "eta": "",
  "isNRI": 0,
  "isCV19": 0,
  "playerid": 27468,
  "mlbamid1": 672282,
  "mlbauto": 3014425,
  "minorbamid": 672282,
  "minormasterid": "sa3014425",
  "playerid1": 27468,
  "mlbamid2": 672282,
  "acquiredrecent": 0,
  "oPlayerId": "27468",
  "season": 2021,
  "playerid2": 27468,
  "prht": 714,
  "prsp": 308,
  "prht7": 663,
  "prsp14": 168,
  "PA": 2,
  "IP": 20.6667,
  "prht2h": 641,
  "prsp2h": 240,
  "Pts": 76.323,
  "IP_minor": 62,
  "AAA_SP_IP": 8,
  "AAA_RP_IP": 8,
  "AA_SP_IP": 54.0000114440918,
  "AA_RP_IP": 54.0000114440918,
  "P_Pts": 76.323,
  "AAA_SP_Pts": 11.0786,
  "AA_SP_Pts": 65.2443,
  "RP_Pts": 0,
  "PA1": 0,
  "Hit_Pts": 0,
  "AAA_SP_Rank": 159,
  "AA_SP_Rank": 6,
  "Overall_Rank": 180,
  "Overall_7_Rank": 520,
  "Overall_14_Rank": 693,
  "Overall_21_Rank": 2878,
  "Overall_1H_Rank": 158,
  "Overall_2H_Rank": 356,
  "Ovr_Rank_Next": 33,
  "Org_Rank_Next": 1,
  "dbTeam": "LAA",
  "playerNameDisplay": "Reid Detmers",
  "playerNameRoute": "Reid Detmers",
  "mlevel": "MLB",
  "proj_PT": 122,
  "proj_WAR": 1.44408,
  "proj_pit_GS": 21,
  "proj_pit_SV": 0,
  "proj_pit_H": 112,
  "proj_pit_SO": 131,
  "proj_pit_BB": 47,
  "proj_pit_ERA": 4.26993,
  "actual_PT": 20.2,
  "actual_WAR": -0.151273,
  "actual_pit_GS": 5,
  "actual_pit_SV": 0,
  "actual_pit_H": 26,
  "actual_pit_SO": 19,
  "actual_pit_BB": 11,
  "actual_pit_ERA": 7.40323,
  "actual_bat_K%": 0.5,
  "actual_bat_HR": 0,
  "actual_bat_SB": 0,
  "actual_bat_AVG": 0,
  "actual_bat_OBP": 0.5,
  "actual_bat_SLG": 0,
  "actual_bat_OPS": 0.5,
  "actual_bat_WRC+": 119.474,
  "actual_bat_Events": 0,
  "actual_bat_BB%": 0.5,
  "actual_bat_K%1": 1,
  "actual_bat_pivFA": 95.2415,
  "actual_bat_piFA%": 0.8,
  "actual_bat_piFC%": 0.2,
  "actual_pit_Events": 69,
  "actual_pit_EV": 88.8227,
  "actual_pit_Barrel%": 0.115942,
  "actual_pit_HardHit%": 0.333333,
  "actual_pit_BB%": 0.108911,
  "actual_pit_K%": 0.188119,
  "actual_pit_pivFA": 92.9212,
  "actual_pit_piFA%": 0.451187,
  "actual_pit_piSL%": 0.240106,
  "actual_pit_piCU%": 0.261214,
  "actual_pit_piCH%": 0.0474934
}
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
                        if player.get(id_type, None) and player.get("playerid1", None):
                            try:
                                p = models.Player.objects.get(fg_id=player[id_type])
                                p.fg_id = player["playerid1"]

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
            if player.get("playerid1", None):
                fg_id = player["playerid1"]
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
        "playerid1"
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
                    for possible_id in ["playerid1", "oPlayerId", "minormasterid"]:
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
                            p = models.Player.objects.get(fg_id=player["playerid1"])
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
