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
    season = 2025

    def should_skip_player(self, row):
        """Skip player if they have invalid or missing critical data."""
        if not row:
            return True
        
        # Skip if no player ID or name
        if not row.get('Name') and not row.get('playerid'):
            return True
            
        # Skip if name is empty or placeholder
        name = row.get('Name', '').strip()
        if not name or name in ['', 'NA', 'N/A', 'Unknown']:
            return True
            
        return False

    def get_or_create_player(self, row):
        """Find or create a player from FanGraphs data."""
        obj = None
        fg_id = None
        
        # Try to get FG ID from various fields
        if row.get('playerid'):
            fg_id = str(row['playerid']).strip()
        elif row.get('PlayerId'):
            fg_id = str(row['PlayerId']).strip()
        elif row.get('playerid1'):
            fg_id = str(row['playerid1']).strip()
        
        if fg_id and fg_id != '':
            try:
                obj = models.Player.objects.get(fg_id=fg_id)
                return obj
            except models.Player.DoesNotExist:
                pass
        
        # Try to find by name if no FG ID match
        name = row.get('Name', '').strip()
        if name:
            try:
                # Try exact match first
                obj = models.Player.objects.get(name=name)
                # Update FG ID if we found the player
                if fg_id and not obj.fg_id:
                    obj.fg_id = fg_id
                    obj.save()
                return obj
            except models.Player.DoesNotExist:
                pass
            except models.Player.MultipleObjectsReturned:
                # If multiple players with same name, skip for safety
                return None
        
        # Create new player if we have enough info
        if fg_id and name:
            obj = models.Player()
            obj.name = name
            obj.fg_id = fg_id
            obj.level = "B"  # Default level
            
            # Set position if available
            position = row.get('Pos', row.get('Position', ''))
            if position and str(position).strip():
                obj.position = utils.normalize_pos(position)
            else:
                obj.position = "DH"  # Default for unknown positions
            
            # Set age if available
            age_str = str(row.get('Age', '')).strip()
            if age_str and age_str not in ['', 'NA', 'N/A']:
                try:
                    obj.raw_age = int(float(age_str.split('.')[0]))
                except (ValueError, IndexError):
                    pass
            
            obj.save()
            return obj
        
        return None

    def build_hitter_stats_dict(self, row, league_type):
        """Build a stats dictionary for hitters."""
        if not row:
            return None
            
        stats_dict = {
            'type': league_type,
            'timestamp': utils.generate_timestamp(),
            'script': 'live_update_stats_from_fg_stats',
            'host': utils.get_hostname(),
        }
        
        # Map common hitting stats
        stat_mappings = {
            'G': ['G', 'Games'],
            'PA': ['PA'],
            'AB': ['AB'],
            'R': ['R', 'Runs'],
            'H': ['H', 'Hits'],
            '2B': ['2B', 'Doubles'],
            '3B': ['3B', 'Triples'],
            'HR': ['HR'],
            'RBI': ['RBI'],
            'SB': ['SB'],
            'CS': ['CS'],
            'BB': ['BB'],
            'SO': ['SO', 'K'],
            'AVG': ['AVG'],
            'OBP': ['OBP'],
            'SLG': ['SLG'],
            'OPS': ['OPS'],
            'wOBA': ['wOBA'],
            'wRC+': ['wRC+', 'wRC_plus'],
            'WAR': ['WAR'],
        }
        
        for stat_key, possible_fields in stat_mappings.items():
            for field in possible_fields:
                if field in row and row[field] not in ['', None, 'NA', 'N/A']:
                    try:
                        value = row[field]
                        if stat_key in ['AVG', 'OBP', 'SLG', 'OPS', 'wOBA', 'WAR']:
                            stats_dict[stat_key] = float(value)
                        else:
                            stats_dict[stat_key] = int(float(value))
                        break
                    except (ValueError, TypeError):
                        continue
        
        # Only return if we have meaningful stats
        if stats_dict.get('PA') or stats_dict.get('AB') or stats_dict.get('G'):
            return stats_dict
        
        return None

    def build_pitcher_stats_dict(self, row, league_type):
        """Build a stats dictionary for pitchers."""
        if not row:
            return None
            
        stats_dict = {
            'type': league_type,
            'timestamp': utils.generate_timestamp(),
            'script': 'live_update_stats_from_fg_stats',
            'host': utils.get_hostname(),
        }
        
        # Map common pitching stats
        stat_mappings = {
            'G': ['G', 'Games'],
            'GS': ['GS'],
            'W': ['W'],
            'L': ['L'],
            'SV': ['SV'],
            'IP': ['IP'],
            'H': ['H', 'Hits'],
            'R': ['R', 'Runs'],
            'ER': ['ER'],
            'HR': ['HR'],
            'BB': ['BB'],
            'SO': ['SO', 'K'],
            'ERA': ['ERA'],
            'WHIP': ['WHIP'],
            'FIP': ['FIP'],
            'WAR': ['WAR'],
            'K/9': ['K/9', 'K_9'],
            'BB/9': ['BB/9', 'BB_9'],
        }
        
        for stat_key, possible_fields in stat_mappings.items():
            for field in possible_fields:
                if field in row and row[field] not in ['', None, 'NA', 'N/A']:
                    try:
                        value = row[field]
                        if stat_key == 'IP':
                            # Handle IP format like "123.1" -> 123
                            stats_dict[stat_key] = int(float(value))
                        elif stat_key in ['ERA', 'WHIP', 'FIP', 'WAR', 'K/9', 'BB/9']:
                            stats_dict[stat_key] = float(value)
                        else:
                            stats_dict[stat_key] = int(float(value))
                        break
                    except (ValueError, TypeError):
                        continue
        
        # Only return if we have meaningful stats
        if stats_dict.get('IP') or stats_dict.get('G') or stats_dict.get('GS'):
            return stats_dict
        
        return None

    def _save_player_stat_season(self, obj, season, stats_dict, stats_type):
        """Save stats to PlayerStatSeason model instead of Player.stats."""
        # Map stats types to PlayerStatSeason classifications
        classification_map = {
            'majors': '1-majors',
            'minors': '2-minors', 
            'amateur': '5-ncaa',
            'pro': '3-npb',  # Default for international pro
        }
        
        # Handle special international leagues
        if stats_type == 'pro':
            if stats_dict.get('League') == 'NPB':
                classification = '3-npb'
            elif stats_dict.get('League') == 'KBO':
                classification = '4-kbo'
            else:
                classification = '3-npb'  # Default
        else:
            classification = classification_map.get(stats_type, '2-minors')
        
        # Determine if this is minors vs majors
        minors = classification != '1-majors'
        
        # Get or create PlayerStatSeason
        player_stat_season, created = models.PlayerStatSeason.objects.get_or_create(
            player=obj,
            season=season,
            classification=classification,
            defaults={
                'minors': minors,
                'carded': False,  # Will be set by separate command
                'owned': obj.is_owned,  # Set ownership based on player
            }
        )
        
        # Update stats
        if obj.position == 'P':
            player_stat_season.pitch_stats = stats_dict
        else:
            player_stat_season.hit_stats = stats_dict
        
        # Update ownership if it has changed
        if player_stat_season.owned != obj.is_owned:
            player_stat_season.owned = obj.is_owned
        
        player_stat_season.save()
        
        return player_stat_season

    def set_mlb_hitter_season(self):
        """Load the stats for Major League Hitters this season."""
        local_path = f"data/{self.season}/fg_mlb_bat.json"
        rows = utils.s3_manager.get_file_content(local_path)
        
        if not rows:
            self.stderr.write(f"Could not find MLB batting data for {self.season}")
            return
            
        for row in rows:
            if self.should_skip_player(row):
                continue

            obj = self.get_or_create_player(row)
            if not obj:
                continue

            stats_dict = self.build_hitter_stats_dict(row, 'majors')
            if stats_dict:
                # Update PlayerStatSeason only
                self._save_player_stat_season(obj, self.season, stats_dict, stats_dict['type'])
                obj.save()

    def set_mlb_pitcher_season(self):
        """Load the stats for Major League Pitchers this season."""
        local_path = f"data/{self.season}/fg_mlb_pit.json"
        rows = utils.s3_manager.get_file_content(local_path)
        
        if not rows:
            self.stderr.write(f"Could not find MLB pitching data for {self.season}")
            return

        for row in rows:
            if self.should_skip_player(row):
                continue

            obj = self.get_or_create_player(row)
            if not obj:
                continue

            stats_dict = self.build_pitcher_stats_dict(row, 'majors')
            if stats_dict:
                # Update PlayerStatSeason only
                self._save_player_stat_season(obj, self.season, stats_dict, stats_dict['type'])
                obj.save()

    def set_minor_hitter_season(self):
        """Load the stats for Minor League Hitters this season."""
        local_path = f"data/{self.season}/fg_milb_bat.json"
        rows = utils.s3_manager.get_file_content(local_path)
        
        if not rows:
            self.stderr.write(f"Could not find Minor League batting data for {self.season}")
            return

        for row in rows:
            if self.should_skip_player(row):
                continue

            obj = self.get_or_create_player(row)
            if obj:
                stats_dict = self.build_hitter_stats_dict(row, 'minors')
                if stats_dict:
                    # Update PlayerStatSeason only
                    self._save_player_stat_season(obj, self.season, stats_dict, stats_dict['type'])
                    obj.save()

    def set_minor_pitcher_season(self):
        """Load the stats for Minor League Pitchers this season."""
        local_path = f"data/{self.season}/fg_milb_pit.json"
        rows = utils.s3_manager.get_file_content(local_path)
        
        if not rows:
            self.stderr.write(f"Could not find Minor League pitching data for {self.season}")
            return

        for row in rows:
            if self.should_skip_player(row):
                continue

            obj = self.get_or_create_player(row)
            if obj:
                stats_dict = self.build_pitcher_stats_dict(row, 'minors')
                if stats_dict:
                    # Update PlayerStatSeason only
                    self._save_player_stat_season(obj, self.season, stats_dict, stats_dict['type'])
                    obj.save()

    def set_college_hitter_season(self):
        """Load the stats for College Hitters this season."""
        local_path = f"data/{self.season}/fg_college_bat.json"
        rows = utils.s3_manager.get_file_content(local_path)
        
        if not rows:
            self.stderr.write(f"Could not find college batting data for {self.season}")
            return

        for row in rows:
            if self.should_skip_player(row):
                continue

            obj = self.get_or_create_player(row)
            if obj:
                stats_dict = self.build_hitter_stats_dict(row, 'amateur')
                if stats_dict:
                    # Update PlayerStatSeason only
                    self._save_player_stat_season(obj, self.season, stats_dict, stats_dict['type'])
                    obj.save()

    def set_college_pitcher_season(self):
        """Load the stats for College Pitchers this season."""
        local_path = f"data/{self.season}/fg_college_pit.json"
        rows = utils.s3_manager.get_file_content(local_path)
        
        if not rows:
            self.stderr.write(f"Could not find college pitching data for {self.season}")
            return

        for row in rows:
            if self.should_skip_player(row):
                continue

            obj = self.get_or_create_player(row)
            if obj:
                stats_dict = self.build_pitcher_stats_dict(row, 'amateur')
                if stats_dict:
                    # Update PlayerStatSeason only
                    self._save_player_stat_season(obj, self.season, stats_dict, stats_dict['type'])
                    obj.save()

    def set_npb_hitter_season(self):
        """Load the stats for NPB Hitters this season."""
        local_path = f"data/{self.season}/fg_npb_bat.json"
        rows = utils.s3_manager.get_file_content(local_path)
        
        if not rows:
            self.stderr.write(f"Could not find NPB batting data for {self.season}")
            return

        for row in rows:
            if self.should_skip_player(row):
                continue

            obj = self.get_or_create_player(row)
            if obj:
                stats_dict = self.build_hitter_stats_dict(row, 'pro')
                if stats_dict:
                    stats_dict['League'] = 'NPB'  # Set league for classification
                    # Update PlayerStatSeason only
                    self._save_player_stat_season(obj, self.season, stats_dict, stats_dict['type'])
                    obj.save()

    def set_npb_pitcher_season(self):
        """Load the stats for NPB Pitchers this season."""
        local_path = f"data/{self.season}/fg_npb_pit.json"
        rows = utils.s3_manager.get_file_content(local_path)
        
        if not rows:
            self.stderr.write(f"Could not find NPB pitching data for {self.season}")
            return

        for row in rows:
            if self.should_skip_player(row):
                continue

            obj = self.get_or_create_player(row)
            if obj:
                stats_dict = self.build_pitcher_stats_dict(row, 'pro')
                if stats_dict:
                    stats_dict['League'] = 'NPB'  # Set league for classification
                    # Update PlayerStatSeason only
                    self._save_player_stat_season(obj, self.season, stats_dict, stats_dict['type'])
                    obj.save()

    def set_kbo_hitter_season(self):
        """Load the stats for KBO Hitters this season."""
        local_path = f"data/{self.season}/fg_kbo_bat.json"
        rows = utils.s3_manager.get_file_content(local_path)
        
        if not rows:
            self.stderr.write(f"Could not find KBO batting data for {self.season}")
            return

        for row in rows:
            if self.should_skip_player(row):
                continue

            obj = self.get_or_create_player(row)
            if obj:
                stats_dict = self.build_hitter_stats_dict(row, 'pro')
                if stats_dict:
                    stats_dict['League'] = 'KBO'  # Set league for classification
                    # Update PlayerStatSeason only
                    self._save_player_stat_season(obj, self.season, stats_dict, stats_dict['type'])
                    obj.save()

    def set_kbo_pitcher_season(self):
        """Load the stats for KBO Pitchers this season."""
        local_path = f"data/{self.season}/fg_kbo_pit.json"
        rows = utils.s3_manager.get_file_content(local_path)
        
        if not rows:
            self.stderr.write(f"Could not find KBO pitching data for {self.season}")
            return

        for row in rows:
            if self.should_skip_player(row):
                continue

            obj = self.get_or_create_player(row)
            if obj:
                stats_dict = self.build_pitcher_stats_dict(row, 'pro')
                if stats_dict:
                    stats_dict['League'] = 'KBO'  # Set league for classification
                    # Update PlayerStatSeason only
                    self._save_player_stat_season(obj, self.season, stats_dict, stats_dict['type'])
                    obj.save()

    def handle(self, *args, **options):
        # Track successes and failures
        results = {'success': [], 'failed': []}
        
        operations = [
            ('College Hitters', self.set_college_hitter_season),
            ('College Pitchers', self.set_college_pitcher_season),
            ('Minor League Hitters', self.set_minor_hitter_season),
            ('Minor League Pitchers', self.set_minor_pitcher_season),
            ('KBO Hitters', self.set_kbo_hitter_season),
            ('KBO Pitchers', self.set_kbo_pitcher_season),
            ('NPB Hitters', self.set_npb_hitter_season),
            ('NPB Pitchers', self.set_npb_pitcher_season),
            ('MLB Hitters', self.set_mlb_hitter_season),
            ('MLB Pitchers', self.set_mlb_pitcher_season),
        ]
        
        for operation_name, operation_func in operations:
            try:
                print(f'Processing {operation_name}...')
                operation_func()
                results['success'].append(operation_name)
                print(f'✓ {operation_name} completed successfully')
            except Exception as e:
                print(f'✗ ERROR processing {operation_name}: {e}')
                results['failed'].append(f'{operation_name}: {str(e)}')
                # Continue with next operation
                continue
        
        # Print summary
        print('\n' + '='*50)
        print('FG STATS UPDATE SUMMARY')
        print('='*50)
        print(f'✓ Successful ({len(results["success"])}):')
        for item in results['success']:
            print(f'  - {item}')
        
        if results['failed']:
            print(f'\n✗ Failed ({len(results["failed"])}):')
            for item in results['failed']:
                print(f'  - {item}')
        else:
            print('\n✓ All operations completed successfully!')
        print('='*50)
