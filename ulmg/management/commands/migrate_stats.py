import csv
import ujson as json
import os

from dateutil.parser import parse
from django.apps import apps
from django.db import connection
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Count, Avg, Sum, Max, Min, Q
from django.conf import settings

from ulmg import models

try:
    from tqdm import tqdm
    HAS_TQDM = True
except ImportError:
    HAS_TQDM = False


class Command(BaseCommand):
    def handle(self, *args, **options):
        players = models.Player.objects.filter(stats__isnull=False)
        total_players = players.count()
        
        self.stdout.write(f"Migrating stats for {total_players} players...")
        
        if not HAS_TQDM:
            self.stdout.write("For a better progress experience, install tqdm: pip install tqdm")
        
        if HAS_TQDM:
            # Use tqdm progress bar if available
            players_iter = tqdm(players, desc="Migrating player stats", unit="players")
        else:
            # Fallback to simple counter
            players_iter = players
            processed = 0
        
        for p in players_iter:
            for sd in p.stats.items():
                slug = sd[0]
                stats_dict = sd[1]

                season, classification, side = slug.split('_')

                if side == "bat":
                    side = "hit"

                if side == "pit":
                    side = "pitch"

                """
                player = models.ForeignKey(Player, on_delete=models.SET_NULL, blank=True, null=True)
                season = models.IntegerField(blank=True, null=True)
                CLASSIFICATION_CHOICES = (
                    ("1-majors", "1-majors"),
                    ("2-minors", "2-minors"),
                    ("3-npb", "3-npb"),
                    ("4-kbo", "4-kbo"),
                    ("5-ncaa", "5-ncaa"),
                )
                classification = models.CharField(max_length=255, choices=CLASSIFICATION_CHOICES, null=True)
                level = models.CharField(max_length=255, blank=True, null=True)
                hit_stats = models.JSONField(null=True, blank=True)
                pitch_stats = models.JSONField(null=True, blank=True)
                """

                def standardize_classification(classification, level):
                    # Normalize for case-insensitive comparisons
                    classification_lower = classification.lower() if classification else ""
                    level_lower = level.lower() if level else ""
                    
                    # Check for MLB/majors
                    if classification_lower in ["majors", "mlb"] or level_lower in ["majors", "mlb"]:
                        return "1-majors"

                    # Check for NCAA/college FIRST (before minors check to avoid "a" in "ncaa" collision)
                    college_indicators = ["ncaa", "college", "juco", "junior college", "d1", "d2", "d3"]
                    if (classification_lower in college_indicators or 
                        any(indicator in level_lower for indicator in college_indicators)):
                        return "5-ncaa"

                    # Check for minors - more comprehensive check
                    if classification_lower == "minors":
                        return "2-minors"
                    
                    # Use more precise minors level matching to avoid false positives
                    minors_levels = ["dsl", "cpx", "r", "a+", "aa", "aaa"]  # removed bare "a" 
                    for minors_level in minors_levels:
                        if minors_level in level_lower:
                            return "2-minors"
                    
                    # Special case for bare "a" to avoid matching "ncaa", "atlanta", etc.
                    if level_lower == "a" or level_lower.startswith("a ") or level_lower.endswith(" a"):
                        return "2-minors"

                    # Check for international leagues
                    if level_lower == "npb":
                        return "3-npb"

                    if level_lower == "kbo":
                        return "4-kbo"

                    return None

                standardized_classification = standardize_classification(classification, stats_dict['level'])
                pss, created = models.PlayerStatSeason.objects.get_or_create(
                    player=p, 
                    season=season, 
                    classification=standardized_classification, 
                    level=stats_dict['level']
                )

                # Set the new boolean fields
                pss.minors = standardized_classification == "2-minors"
                pss.carded = p.is_carded
                pss.owned = p.is_owned

                if side == "hit":
                    pss.hit_stats = stats_dict

                if side == "pitch":
                    pss.pitch_stats = stats_dict

                pss.save()
            
            # Progress reporting for fallback case (no tqdm)
            if not HAS_TQDM:
                processed += 1
                if processed % 1000 == 0 or processed == total_players:
                    self.stdout.write(f"Processed {processed}/{total_players} players ({processed/total_players*100:.1f}%)")
        
        self.stdout.write(self.style.SUCCESS(f"Successfully migrated stats for {total_players} players!"))