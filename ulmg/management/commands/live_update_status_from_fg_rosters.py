import csv
import json
import os
from decimal import Decimal

from bs4 import BeautifulSoup
from dateutil.parser import parse
from django.apps import apps
from django.db import connection, transaction
from django.db.models import Avg, Sum, Count
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
import requests

from ulmg import models, utils


class Command(BaseCommand):

    def _get_current_season(self):
        """Get the current season year."""
        from datetime import datetime
        return datetime.now().year

    def _update_player_stat_season(self, player, season, **kwargs):
        """Update or create PlayerStatSeason with roster status fields."""
        # Get or create the most recent PlayerStatSeason for this player
        # We'll use the most recent stats record or create a new one for the current season
        player_stat_season = models.PlayerStatSeason.objects.filter(
            player=player
        ).order_by('-season', '-classification').first()
        
        if not player_stat_season:
            # Create a new PlayerStatSeason for the current season
            player_stat_season = models.PlayerStatSeason.objects.create(
                player=player,
                season=season,
                classification='1-majors',  # Default to majors, will be corrected by stats updates
                owned=player.is_owned,
                carded=False  # Will be set by separate command
            )
        
        # Update the roster status fields
        for field, value in kwargs.items():
            if hasattr(player_stat_season, field):
                setattr(player_stat_season, field, value)
        
        player_stat_season.save()
        return player_stat_season

    def handle(self, *args, **options):
        teams = settings.ROSTER_TEAM_IDS
        current_season = self._get_current_season()

        # Clear roster status fields for all current season PlayerStatSeason records
        models.PlayerStatSeason.objects.filter(
            season=current_season
        ).update(
            role_type=None, 
            is_injured=False, 
            role=None, 
            is_starter=False, 
            is_bench=False, 
            injury_description=None, 
            is_mlb40man=False
        )

        for team_id, team_abbrev, team_name in teams:
            local_path = f"data/rosters/{team_abbrev}_roster.json"
            roster = utils.s3_manager.get_file_content(local_path)
            
            if not roster:
                self.stderr.write(f"Could not find roster data for {team_name} ({team_abbrev})")
                continue

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
                    obj.fg_id = fg_id
                    obj.mlbam_id = mlbam_id
                    # Handle #N/A values in age data
                    age_str = str(player['age']).strip()
                    if age_str and age_str != '#N/A' and age_str != '':
                        try:
                            obj.raw_age = int(float(age_str.split('.')[0]))
                        except (ValueError, IndexError):
                            obj.raw_age = None
                    else:
                        obj.raw_age = None
                    obj.save()  # Save player first
                    print(f"+++ {obj}")

                # Prepare roster status updates for PlayerStatSeason
                roster_updates = {
                    'is_injured': False,
                    'role': None,
                    'is_starter': False,
                    'is_bench': False,
                    'injury_description': None,
                    'is_mlb40man': False,
                    'role_type': None,
                    'mlb_org': team_abbrev
                }

                if player.get("mlevel", None):
                    roster_updates['role'] = player["mlevel"]
                elif player.get("role", None):
                    if player["role"].strip() != "":
                        roster_updates['role'] = player["role"]

                if roster_updates['role'] == "MLB":
                    roster_updates['is_mlb40man'] = True

                if player.get('type', None):
                    if player["type"] == "mlb-bp":
                        roster_updates['is_bullpen'] = True

                    if player["type"] == "mlb-sp":
                        roster_updates['is_starter'] = True

                    if player["type"] == "mlb-bn":
                        roster_updates['is_bench'] = True

                    if player["type"] == "mlb-sl":
                        roster_updates['is_starter'] = True

                    roster_updates['role_type'] = player['type']

                roster_updates['injury_description'] = player.get("injurynotes", None)

                if player.get('roster40', None):
                    if player["roster40"] == "Y":
                        roster_updates['is_mlb40man'] = True

                # Update PlayerStatSeason instead of Player
                self._update_player_stat_season(obj, current_season, **roster_updates)
                print(f"Updated roster status for {obj}")