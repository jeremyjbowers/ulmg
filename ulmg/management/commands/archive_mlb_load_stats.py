# ABOUTME: ARCHIVED - Original load_mlb_stats. See documents/MLB_DATA_PIPELINE_RECOMMENDATION.md
# ABOUTME: Uses python-mlb-statsapi to fetch stats for players with mlbam_id, populates PlayerStatSeason.
import logging
from django.core.management.base import BaseCommand
from django.db import transaction
from ulmg.models import Player, PlayerStatSeason
import mlbstatsapi

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Load MLB stats for players with mlbam_id using python-mlb-statsapi (ARCHIVED)'

    def add_arguments(self, parser):
        parser.add_argument('--season', type=int)
        parser.add_argument('--player-id', type=str)
        parser.add_argument('--limit', type=int, default=None)
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        from ulmg import utils
        season = options.get('season') or utils.get_current_season()
        players = list(Player.objects.filter(mlbam_id__isnull=False).exclude(mlbam_id=''))
        if options.get('player_id'):
            players = [p for p in players if p.mlbam_id == options['player_id']]
        if options.get('limit'):
            players = players[:options['limit']]
        for player in players:
            try:
                stats_data = self._get_player_stats(player.mlbam_id, season)
                if stats_data and not options.get('dry_run'):
                    self._save_player_stats(player, season, stats_data)
            except Exception as e:
                logger.exception(f"Error: {player.name}")

    def _get_player_stats(self, mlbam_id, season):
        mlb = mlbstatsapi.Mlb()
        stats_data = {'hitting': {}, 'pitching': {}}
        try:
            hitting_stats = mlb.get_player_stats(mlbam_id, stats=['season'], groups=['hitting'], season=season)
            if hitting_stats and 'hitting' in hitting_stats and 'season' in hitting_stats['hitting']:
                stats_data['hitting'] = self._parse_hitting_stats(hitting_stats['hitting']['season'])
        except Exception:
            pass
        try:
            pitching_stats = mlb.get_player_stats(mlbam_id, stats=['season'], groups=['pitching'], season=season)
            if pitching_stats and 'pitching' in pitching_stats and 'season' in pitching_stats['pitching']:
                stats_data['pitching'] = self._parse_pitching_stats(pitching_stats['pitching']['season'])
        except Exception:
            pass
        return stats_data if any(stats_data.values()) else None

    def _parse_hitting_stats(self, hitting_season):
        if not hitting_season or not hasattr(hitting_season, 'splits') or not hitting_season.splits:
            return {}
        split = hitting_season.splits[0]
        stat = split.stat
        pa = getattr(stat, 'plateappearances', 0) or 0
        return {
            'plate_appearances': pa,
            'ab': getattr(stat, 'atbats', 0) or 0,
            'hits': getattr(stat, 'hits', 0) or 0,
            '2b': getattr(stat, 'doubles', 0) or 0,
            '3b': getattr(stat, 'triples', 0) or 0,
            'hr': getattr(stat, 'homeruns', 0) or 0,
            'runs': getattr(stat, 'runs', None),
            'rbi': getattr(stat, 'rbi', None),
            'sb': getattr(stat, 'stolenbases', None),
            'avg': getattr(stat, 'avg', None),
            'obp': getattr(stat, 'obp', None),
            'slg': getattr(stat, 'slg', None),
        }

    def _parse_pitching_stats(self, pitching_season):
        if not pitching_season or not hasattr(pitching_season, 'splits') or not pitching_season.splits:
            return {}
        split = pitching_season.splits[0]
        stat = split.stat
        ip = getattr(stat, 'inningspitched', 0) or 0
        return {
            'g': getattr(stat, 'gamesplayed', None),
            'gs': getattr(stat, 'gamesstarted', None),
            'ip': ip,
            'k': getattr(stat, 'strikeouts', 0) or 0,
            'bb': getattr(stat, 'baseonballs', 0) or 0,
            'wins': getattr(stat, 'wins', None),
            'losses': getattr(stat, 'losses', None),
            'saves': getattr(stat, 'saves', None),
            'era': getattr(stat, 'era', None),
        }

    def _save_player_stats(self, player, season, stats_data):
        with transaction.atomic():
            stat_season, created = PlayerStatSeason.objects.get_or_create(
                player=player,
                season=season,
                classification="1-majors",
                defaults={'level': 'MLB', 'minors': False, 'carded': season >= 2025, 'owned': player.is_owned}
            )
            if stats_data.get('hitting'):
                stat_season.hit_stats = stats_data['hitting']
            if stats_data.get('pitching'):
                stat_season.pitch_stats = stats_data['pitching']
            stat_season.save()
