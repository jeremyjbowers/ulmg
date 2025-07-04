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
    def match_ids_from_rosters(self):
        teams = settings.ROSTER_TEAM_IDS
        
        # Track successes and failures
        results = {'success': [], 'failed': [], 'players_processed': 0, 'players_failed': 0}

        for team_id, team_abbrev, team_name in teams:
            try:
                print(f"Processing {team_name} ({team_abbrev})...")
                
                local_path = f"data/rosters/{team_abbrev}_roster.json"
                try:
                    roster = utils.s3_manager.get_file_content(local_path)
                    if not roster:
                        # Fallback to local file
                        with open(local_path, "r") as readfile:
                            roster = json.loads(readfile.read())
                except FileNotFoundError:
                    print(f"ERROR: Roster file not found for {team_name}: {local_path}")
                    results['failed'].append(f"{team_name}: Roster file not found")
                    continue

                team_players_processed = 0
                for player in roster:
                    try:
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

                        # player has a minormasterid in the fg_id and needs updating
                        # a player's initial fg_id is a minormaster id like sa12345
                        # but once they get to the majors, they get a new id like 987654
                        # so we need a way to catch these changes and update the old fg_id
                        if player.get("minormasterid", None) and fg_id:
                            obj = models.Player.objects.filter(fg_id=player["minormasterid"])

                            # only do this for players whose fg_id is now different from their minormasterid
                            if player["minormasterid"] != fg_id:
                                if len(obj) == 1:
                                    obj = obj[0]
                                    obj.fg_id = fg_id
                                    obj.save()
                                    print(f"+ minormasterid {obj}")

                        # player has an fg_id but no mlbam_id yet
                        # we occasionally will have players who have been loaded via fg but no mlbam_id
                        if mlbam_id and fg_id:
                            obj = models.Player.objects.filter(fg_id=fg_id)

                            if len(obj) == 1:
                                obj = obj[0]

                                # only do this for players missing an mlbam_id
                                if not obj.mlbam_id:
                                    obj.mlbam_id = mlbam_id
                                    obj.save()
                                    print(f"+ mlbam_id {obj}")


                        # player has an mlbamid but no fg_id yet
                        # since we load players from MLB.com rosters
                        # we will occasionally have debutees show up with mlbam_ids but no fg_id
                        # this lets us get stats for them from fg
                        if mlbam_id and fg_id:
                            obj = models.Player.objects.filter(mlbam_id=mlbam_id)

                            if len(obj) == 1:
                                obj = obj[0]

                                # only do this for players missing an fg_id
                                if not obj.fg_id:
                                    obj.fg_id = fg_id
                                    obj.save()
                                    print(f"+ fg_id {obj}")

                        team_players_processed += 1
                        results['players_processed'] += 1
                        
                    except Exception as e:
                        player_name = player.get('player', 'Unknown') if isinstance(player, dict) else 'Unknown'
                        print(f"ERROR processing player {player_name} for {team_name}: {e}")
                        results['players_failed'] += 1
                        continue

                results['success'].append(f"{team_name}: {team_players_processed} players processed")
                print(f"✓ {team_name}: {team_players_processed} players processed")
                
            except Exception as e:
                print(f"✗ ERROR processing team {team_name}: {e}")
                results['failed'].append(f"{team_name}: {str(e)}")
                continue

        # Print summary
        print('\n' + '='*50)
        print('ID CROSSWALK SUMMARY')
        print('='*50)
        print(f'Players processed: {results["players_processed"]}')
        print(f'Players failed: {results["players_failed"]}')
        print(f'\n✓ Successful teams ({len(results["success"])}):')
        for item in results['success']:
            print(f'  - {item}')
        
        if results['failed']:
            print(f'\n✗ Failed teams ({len(results["failed"])}):')
            for item in results['failed']:
                print(f'  - {item}')
        else:
            print('\n✓ All teams processed successfully!')
        print('='*50)


    def handle(self, *args, **options):
        requests.packages.urllib3.disable_warnings()
        season = utils.get_current_season()
        self.match_ids_from_rosters()