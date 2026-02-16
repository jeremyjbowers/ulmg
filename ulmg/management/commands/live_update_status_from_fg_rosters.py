# ABOUTME: Updates player roster status from FanGraphs roster JSON files.
# ABOUTME: Creates missing players when FG ID or MLB ID is available.
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
    def get_or_create_player_stat_season(self, player, season, **kwargs):
        """Get or create PlayerStatSeason for a player and season with given updates"""
        classification = kwargs.pop('classification')

        with transaction.atomic():
            player_stat_season, created = models.PlayerStatSeason.objects.get_or_create(
                player=player,
                season=season,
                classification=classification,
                defaults=kwargs
            )

            if not created:
                # Update existing record with provided data
                for key, value in kwargs.items():
                    setattr(player_stat_season, key, value)
                player_stat_season.save()

        return player_stat_season

    def create_player_from_fg_roster(self, player_data, fg_id, mlbam_id):
        """
        Create a Player when one cannot be found. Requires at least fg_id or mlbam_id.
        Returns the created Player or None on error.
        """
        if not fg_id and not mlbam_id:
            return None

        name = player_data.get('player', '').strip()
        if not name:
            return None

        position_raw = player_data.get('position') or player_data.get('position1', '')
        position = utils.normalize_pos(position_raw) if position_raw else 'DH'

        with transaction.atomic():
            player = models.Player(
                name=name,
                position=position,
                level=models.Player.B_LEVEL,
                fg_id=fg_id or None,
                mlbam_id=mlbam_id or None,
                current_mlb_org=player_data.get('dbTeam') or None,
            )
            player.save()
        return player

    def map_fg_role_to_status(self, role, mlevel):
        """Map FanGraphs role and mlevel to our roster status"""
        if not role:
            return "UNKNOWN"
            
        role_upper = role.upper()
        mlevel_upper = mlevel.upper() if mlevel else ""
        
        # Injury list mappings
        if 'IL' in role_upper or 'INJ' in role_upper:
            if '7' in role_upper:
                return "IL-7"
            elif '10' in role_upper:
                return "IL-10"
            elif '15' in role_upper:
                return "IL-15"
            elif '60' in role_upper:
                return "IL-60"
            else:
                return "IL"
        
        # Level-based mappings
        if mlevel_upper == "MLB":
            return "MLB"
        elif mlevel_upper in ["AAA", "AA", "A+", "A", "A-"]:
            return "MINORS"
        elif mlevel_upper in ["RK", "RK2", "SS"]:
            return "ROOKIE"
        else:
            return "MINORS"  # Default for unknown levels

    def handle(self, *args, **options):
        current_season = utils.get_current_season()
        teams = settings.ROSTER_TEAM_IDS
        
        # Track successes and failures
        results = {'success': [], 'failed': [], 'players_processed': 0, 'players_created': 0, 'players_failed': 0}
        
        print(f"Processing FG roster status updates for {current_season} season...")

        for team_id, team_abbrev, team_name in teams:
            try:
                print(f"Processing {team_name} ({team_abbrev})...")
                
                # Load roster data
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
                for player_data in roster:
                    try:
                        # Extract IDs from various fields
                        fg_id = None
                        mlbam_id = None
                        
                        # Try multiple FG ID fields
                        for fg_field in ['oPlayerId', 'playerid', 'playerid1', 'playerid2']:
                            if player_data.get(fg_field):
                                fg_id = str(player_data[fg_field]).strip()
                                if fg_id and fg_id != "":
                                    break
                        
                        # Try multiple MLB ID fields
                        for mlb_field in ['mlbamid', 'mlbamid1', 'mlbamid2', 'minorbamid']:
                            if player_data.get(mlb_field):
                                mlbam_id = str(player_data[mlb_field]).strip()
                                if mlbam_id and mlbam_id != "":
                                    break
                        
                        # Try to find player by FG ID first, then MLB ID
                        player_obj = None
                        if fg_id:
                            try:
                                player_obj = models.Player.objects.get(fg_id=fg_id)
                            except models.Player.DoesNotExist:
                                pass
                        
                        if not player_obj and mlbam_id:
                            try:
                                player_obj = models.Player.objects.get(mlbam_id=mlbam_id)
                            except models.Player.DoesNotExist:
                                pass

                        # Create player if not found but we have FG ID or MLB ID
                        if not player_obj and (fg_id or mlbam_id):
                            player_obj = self.create_player_from_fg_roster(player_data, fg_id, mlbam_id)
                            if player_obj:
                                results['players_created'] += 1
                                print(f"Created player: {player_obj.name} (FG: {fg_id}, MLB: {mlbam_id})")
                        
                        if player_obj:
                            # Map FG data to our fields
                            role = player_data.get('role', '')
                            mlevel = player_data.get('mlevel', '')
                            roster_status = self.map_fg_role_to_status(role, mlevel)

                            # Determine correct classification from mlevel
                            mlevel_upper = mlevel.upper() if mlevel else ""
                            if mlevel_upper == 'MLB':
                                classification = '1-mlb'
                                is_mlb = True
                                is_minors = False
                            else:
                                classification = '2-milb'
                                is_mlb = False
                                is_minors = True
                            
                            # Update player-level organization field
                            if player_data.get('dbTeam'):
                                player_obj.current_mlb_org = player_data['dbTeam']
                                player_obj.save()
                            
                            # Update PlayerStatSeason with roster status
                            # Prefer FanGraphs "type" (e.g., mlb-sl, milb-bn) for role_type
                            fg_type = player_data.get('type', '')

                            season_data = {
                                'roster_status': roster_status,
                                'role': role,
                                'role_type': fg_type or mlevel,
                                'mlb_org': player_data.get('dbTeam', ''),
                                'is_mlb': is_mlb,
                                'minors': is_minors,
                                'is_injured': 'IL' in roster_status or 'INJ' in roster_status,
                                'is_mlb40man': player_data.get('roster40', '').upper() == 'Y',
                            }

                            pss = self.get_or_create_player_stat_season(
                                player_obj, current_season, classification=classification, **season_data
                            )

                            # If this is a minors record, clean up any incorrect 1-mlb record without stats
                            if classification == '2-milb':
                                wrong_mlb = models.PlayerStatSeason.objects.filter(
                                    player=player_obj,
                                    season=current_season,
                                    classification='1-mlb',
                                    hit_stats__isnull=True,
                                    pitch_stats__isnull=True,
                                )
                                if wrong_mlb.exists():
                                    wrong_mlb.delete()
                            
                            print(f"Updated {player_obj.name} - Status: {roster_status}, Org: {season_data['mlb_org']}")
                            team_players_processed += 1
                            results['players_processed'] += 1
                        else:
                            # Player not found: either missing IDs (cannot create) or create failed
                            player_name = player_data.get('player', 'Unknown')
                            if fg_id or mlbam_id:
                                print(f"Player not found (create failed): {player_name} (FG: {fg_id}, MLB: {mlbam_id})")
                            else:
                                print(f"Player skipped (no FG/MLB ID to create): {player_name}")
                        
                    except Exception as e:
                        player_name = player_data.get('player', 'Unknown') if isinstance(player_data, dict) else 'Unknown'
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
        print('FG ROSTER STATUS UPDATE SUMMARY')
        print('='*50)
        print(f'Players processed: {results["players_processed"]}')
        print(f'Players created: {results["players_created"]}')
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