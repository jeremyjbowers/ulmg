"""
Management command to load MLB stats for players with mlbam_id.

This command iterates through all players that have an mlbam_id and uses
the python-mlb-statsapi package to fetch their current season stats,
then populates the PlayerStatSeason model with the required stats
for display in the site's stat tables.
"""

import logging
from django.core.management.base import BaseCommand
from django.db import transaction
from ulmg.models import Player, PlayerStatSeason
import mlbstatsapi

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Load MLB stats for players with mlbam_id using python-mlb-statsapi'

    def add_arguments(self, parser):
        parser.add_argument(
            '--season', 
            type=int, 
            help='Season year to load stats for (default: current season)'
        )
        parser.add_argument(
            '--player-id',
            type=str,
            help='Specific mlbam_id to load stats for (optional)'
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=None,
            help='Limit number of players to process (for testing)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Run without saving to database'
        )

    def handle(self, *args, **options):
        season = options.get('season')
        player_id = options.get('player_id')
        limit = options.get('limit')
        dry_run = options.get('dry_run')
        
        if not season:
            # Default to get_current_season() - uses previous year during offseason
            from ulmg import utils
            season = utils.get_current_season()
        
        self.stdout.write(f'Loading MLB stats for season {season}')
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No data will be saved'))
        
        # Get players with mlbam_id
        players_query = Player.objects.filter(mlbam_id__isnull=False).exclude(mlbam_id='')
        
        if player_id:
            players_query = players_query.filter(mlbam_id=player_id)
            
        if limit:
            players_query = players_query[:limit]
            
        players = list(players_query)
        total_players = len(players)
        
        self.stdout.write(f'Found {total_players} players with mlbam_id')
        
        success_count = 0
        error_count = 0
        
        for i, player in enumerate(players, 1):
            self.stdout.write(f'Processing {i}/{total_players}: {player.name} (ID: {player.mlbam_id})')
            
            try:
                # Get player stats for the season
                stats_data = self._get_player_stats(player.mlbam_id, season)
                
                if stats_data:
                    if not dry_run:
                        self._save_player_stats(player, season, stats_data)
                    
                    self.stdout.write(
                        self.style.SUCCESS(f'  ✓ Loaded stats for {player.name}')
                    )
                    success_count += 1
                else:
                    self.stdout.write(f'  - No stats found for {player.name}')
                    
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'  ✗ Error processing {player.name}: {e}')
                )
                error_count += 1
                logger.exception(f'Error processing player {player.name} (ID: {player.mlbam_id})')
        
        self.stdout.write(
            self.style.SUCCESS(
                f'\nCompleted: {success_count} successful, {error_count} errors'
            )
        )

    def _get_player_stats(self, mlbam_id, season):
        """Fetch player stats from MLB Stats API using python-mlb-statsapi."""
        try:
            mlb = mlbstatsapi.Mlb()
            
            # Get player stats for both hitting and pitching
            stats_data = {
                'hitting': {},
                'pitching': {}
            }
            
            # Try to get hitting stats
            try:
                hitting_stats = mlb.get_player_stats(
                    mlbam_id, 
                    stats=['season'], 
                    groups=['hitting'],
                    season=season
                )
                
                if hitting_stats and 'hitting' in hitting_stats and 'season' in hitting_stats['hitting']:
                    stats_data['hitting'] = self._parse_hitting_stats(hitting_stats['hitting']['season'])
            except Exception as e:
                logger.debug(f'No hitting stats for player {mlbam_id}: {e}')
            
            # Try to get pitching stats
            try:
                pitching_stats = mlb.get_player_stats(
                    mlbam_id, 
                    stats=['season'], 
                    groups=['pitching'],
                    season=season
                )
                
                if pitching_stats and 'pitching' in pitching_stats and 'season' in pitching_stats['pitching']:
                    stats_data['pitching'] = self._parse_pitching_stats(pitching_stats['pitching']['season'])
            except Exception as e:
                logger.debug(f'No pitching stats for player {mlbam_id}: {e}')
            
            # Return stats if we got any data
            if any(stats_data.values()):
                return stats_data
            else:

                return None
                
        except Exception as e:
            logger.error(f'Error fetching stats for player {mlbam_id}: {e}')
            raise

    def _parse_hitting_stats(self, hitting_season):
        """Parse hitting stats from python-mlb-statsapi format."""
        if not hitting_season or not hasattr(hitting_season, 'splits'):
            return {}
        
        # Get the first split (should be season totals)
        if not hitting_season.splits:
            return {}
        
        split = hitting_season.splits[0]
        stat = split.stat
        
        # Extract all available stats from the stat object and convert to proper types
        pa = self._safe_int(getattr(stat, 'plateappearances', 0)) or 0
        ab = self._safe_int(getattr(stat, 'atbats', 0)) or 0
        h = self._safe_int(getattr(stat, 'hits', 0)) or 0
        bb = self._safe_int(getattr(stat, 'baseonballs', 0)) or 0
        k = self._safe_int(getattr(stat, 'strikeouts', 0)) or 0
        doubles = self._safe_int(getattr(stat, 'doubles', 0)) or 0
        triples = self._safe_int(getattr(stat, 'triples', 0)) or 0
        hr = self._safe_int(getattr(stat, 'homeruns', 0)) or 0
        
        # Rate stats
        avg = self._safe_float(getattr(stat, 'avg', None))
        obp = self._safe_float(getattr(stat, 'obp', None))
        slg = self._safe_float(getattr(stat, 'slg', None))
        
        # Calculate ISO if we have the data
        iso = round(slg - avg, 3) if slg and avg else None
        
        return {
            # Counting stats
            'plate_appearances': pa,
            'ab': ab,
            'hits': h,
            '2b': doubles,
            '3b': triples,
            'hr': hr,
            'runs': self._safe_int(getattr(stat, 'runs', None)),
            'rbi': self._safe_int(getattr(stat, 'rbi', None)),
            'sb': self._safe_int(getattr(stat, 'stolenbases', None)),
            
            # Rate stats
            'avg': avg,
            'obp': obp,
            'slg': slg,
            'iso': iso,
            'k_pct': round((k / pa * 100), 1) if pa > 0 else None,
            'bb_pct': round((bb / pa * 100), 1) if pa > 0 else None,
            
            # Advanced stats (these may be available in python-mlb-statsapi)
            'wrc_plus': self._safe_int(getattr(stat, 'wrcplus', None)),
            'xavg': self._safe_float(getattr(stat, 'expectedavg', None) or getattr(stat, 'xavg', None)),
            'xwoba': self._safe_float(getattr(stat, 'expectedwoba', None) or getattr(stat, 'xwoba', None)),
            'xslg': self._safe_float(getattr(stat, 'expectedslg', None) or getattr(stat, 'xslg', None)),
            'babip': self._safe_float(getattr(stat, 'babip', None)),
            'woba': self._safe_float(getattr(stat, 'woba', None)),
            'barrel_pct': self._safe_float(getattr(stat, 'barrelpct', None) or getattr(stat, 'barrelpercent', None)),
            'hard_hit_pct': self._safe_float(getattr(stat, 'hardhitpct', None) or getattr(stat, 'hardhitpercent', None)),
            'max_exit_velocity': self._safe_float(getattr(stat, 'maxexitvelocity', None)),
            'avg_exit_velocity': self._safe_float(getattr(stat, 'avgexitvelocity', None)),
        }
    
    def _parse_pitching_stats(self, pitching_season):
        """Parse pitching stats from python-mlb-statsapi format."""
        if not pitching_season or not hasattr(pitching_season, 'splits'):
            return {}
        
        # Get the first split (should be season totals)
        if not pitching_season.splits:
            return {}
        
        split = pitching_season.splits[0]
        stat = split.stat
        
        # Extract all available stats from the stat object and convert to proper types
        ip = self._safe_float(getattr(stat, 'inningspitched', 0)) or 0
        h_allowed = self._safe_int(getattr(stat, 'hits', 0)) or 0
        bb_allowed = self._safe_int(getattr(stat, 'baseonballs', 0)) or 0
        k = self._safe_int(getattr(stat, 'strikeouts', 0)) or 0
        hr_allowed = self._safe_int(getattr(stat, 'homeruns', 0)) or 0
        
        # Calculate WHIP
        whip = round((h_allowed + bb_allowed) / ip, 3) if ip > 0 else None
        
        # Calculate K/BB ratio
        k_bb = round(k / bb_allowed, 2) if bb_allowed > 0 else None
        
        return {
            # Counting stats
            'g': self._safe_int(getattr(stat, 'gamesplayed', None)),
            'gs': self._safe_int(getattr(stat, 'gamesstarted', None)),
            'ip': ip,
            'hits_allowed': h_allowed,
            'bb': bb_allowed,
            'k': k,
            'hr_allowed': hr_allowed,
            'wins': self._safe_int(getattr(stat, 'wins', None)),
            'losses': self._safe_int(getattr(stat, 'losses', None)),
            'saves': self._safe_int(getattr(stat, 'saves', None)),
            'holds': self._safe_int(getattr(stat, 'holds', None)),
            
            # Rate stats
            'era': self._safe_float(getattr(stat, 'era', None)),
            'whip': whip,
            'k_9': round((k * 9 / ip), 1) if ip > 0 else None,
            'bb_9': round((bb_allowed * 9 / ip), 1) if ip > 0 else None,
            'hr_9': round((hr_allowed * 9 / ip), 1) if ip > 0 else None,
            'k_bb': k_bb,
            'avg_against': self._safe_float(getattr(stat, 'battersfaced', None)),
            
            # Advanced stats (check if available in python-mlb-statsapi)
            'fip': self._safe_float(getattr(stat, 'fip', None)),
            'xfip': self._safe_float(getattr(stat, 'xfip', None)),
            'siera': self._safe_float(getattr(stat, 'siera', None)),
            'xera': self._safe_float(getattr(stat, 'xera', None)),
            'stuff_plus': self._safe_int(getattr(stat, 'stuffplus', None)),
            'location_plus': self._safe_int(getattr(stat, 'locationplus', None)),
        }

    def _save_player_stats(self, player, season, stats_data):
        """Save stats to PlayerStatSeason model."""
        with transaction.atomic():
            # Determine if player should be marked as carded (true for 2025 stats)
            is_carded = season >= 2025
            
            # Get or create PlayerStatSeason record
            stat_season, created = PlayerStatSeason.objects.get_or_create(
                player=player,
                season=season,
                classification="1-majors",
                defaults={
                    'level': 'MLB',
                    'minors': False,
                    'carded': is_carded,
                    'owned': player.is_owned,
                }
            )
            
            # Update the carded status if this is an existing record
            if not created:
                stat_season.carded = is_carded
            
            # Update hitting stats if available
            if stats_data['hitting'] and any(v is not None for v in stats_data['hitting'].values()):
                stat_season.hit_stats = stats_data['hitting']
            
            # Update pitching stats if available
            if stats_data['pitching'] and any(v is not None for v in stats_data['pitching'].values()):
                stat_season.pitch_stats = stats_data['pitching']
            
            # Also update the player's is_carded field if loading 2025+ stats
            if is_carded and not player.is_carded:
                player.is_carded = True
                player.save(update_fields=['is_carded'])
            
            stat_season.save()

    def _safe_int(self, value):
        """Safely convert value to int."""
        if value is None or value == '':
            return None
        try:
            return int(value)
        except (ValueError, TypeError):
            return None

    def _safe_float(self, value):
        """Safely convert value to float."""
        if value is None or value == '':
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None 