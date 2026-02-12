from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from django.db.models import Count

from ulmg import models, utils


class Command(BaseCommand):
    def handle(self, *args, **options):
        teams = [t for t in models.Team.objects.all()]
        print('team,>130,>120,>110,>100')
        for team in teams:
            wrc_buckets = {
                "greater than 130": {
                    "wrc_threshold": 130,
                    "pa": 0,
                    "positions": set([]),
                    "players": [],
                    "num_players": 0
                },
                "greater than 120": {
                    "wrc_threshold": 120,
                    "pa": 0,
                    "positions": set([]),
                    "players": [],
                    "num_players": 0
                },
                "greater than 110": {
                    "wrc_threshold": 110,
                    "pa": 0,
                    "positions": set([]),
                    "players": [],
                    "num_players": 0
                },
                "greater than 100": {
                    "wrc_threshold": 100,
                    "pa": 0,
                    "positions": set([]),
                    "players": [],
                    "num_players": 0
                },
            }
            
            # Get team players with current season major league hitting stats and >= 5 PA
            season = utils.get_current_season()
            team_players = models.Player.objects.filter(team=team)

            for bucket, data in wrc_buckets.items():
                wrc_threshold = data['wrc_threshold']

                # Find PlayerStatSeason objects for current season majors hitting with sufficient PA and wRC+
                qualifying_stat_seasons = models.PlayerStatSeason.objects.filter(
                    player__team=team,
                    season=season,
                    classification='1-mlb',
                    hit_stats__pa__gte=5,
                    hit_stats__wrc_plus__gte=wrc_threshold
                ).select_related('player')
                
                for stat_season in qualifying_stat_seasons:
                    player = stat_season.player
                    hit_stats = stat_season.hit_stats
                    
                    data['pa'] += hit_stats.get('pa', 0)
                    data['positions'].add(player.position)
                    data['num_players'] += 1
                    data['players'].append(player.name)

            team_row = [team.abbreviation]

            for bucket, data in wrc_buckets.items():
                team_row.append(f"{data['pa']}")

            print(",".join(team_row))
