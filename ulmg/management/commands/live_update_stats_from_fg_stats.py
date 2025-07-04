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
        self.set_college_hitter_season()
        self.set_college_pitcher_season()
        self.set_minor_hitter_season()
        self.set_minor_pitcher_season()
        self.set_kbo_hitter_season()
        self.set_kbo_pitcher_season()
        self.set_npb_hitter_season()
        self.set_npb_pitcher_season()
        self.set_mlb_hitter_season()
        self.set_mlb_pitcher_season()
