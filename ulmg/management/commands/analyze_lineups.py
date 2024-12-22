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
                    "filter": {
                        "stats__2024_majors_hit__wrc_plus__gte": 130 
                    },
                    "plate_appearances": 0,
                    "positions": set([]),
                    "players": [],
                    "num_players": 0
                },
                "greater than 120": {
                    "filter": {
                        "stats__2024_majors_hit__wrc_plus__gte": 120 
                    },
                    "plate_appearances": 0,
                    "positions": set([]),
                    "players": [],
                    "num_players": 0
                },
                "greater than 110": {
                    "filter": {
                        "stats__2024_majors_hit__wrc_plus__gte": 110 
                    },
                    "plate_appearances": 0,
                    "positions": set([]),
                    "players": [],
                    "num_players": 0
                },
                "greater than 100": {
                    "filter": {
                        "stats__2024_majors_hit__wrc_plus__gte": 100 
                    },
                    "plate_appearances": 0,
                    "positions": set([]),
                    "players": [],
                    "num_players": 0
                },
                # "greater than 90": {
                #     "filter": {
                #         "stats__2024_majors_hit__wrc_plus__gte": 90 
                #     },
                #     "plate_appearances": 0,
                #     "positions": set([]),
                #     "players": [],
                #     "num_players": 0
                # },
                # "below 90": {
                #     "filter": {
                #         "stats__2024_majors_hit__wrc_plus__lt": 90 
                #     },
                #     "plate_appearances": 0,
                #     "positions": set([]),
                #     "players": [],
                #     "num_players": 0
                # },
            }
            team_players = models.Player.objects.filter(team=team).filter(stats__2024_majors_hit__plate_appearances__gte=5)

            for bucket,data in wrc_buckets.items():
                bucket_players = team_players.filter(**data['filter'])
                for player in bucket_players:
                    data['plate_appearances'] += player.stats['2024_majors_hit']['plate_appearances']
                    data['positions'].add(player.position)
                    # for pos in player.defense:
                    #     data['positions'].add(pos.split('-')[0])
                    data['num_players'] += 1
                    data['players'].append(player.name)

            team_row = [team.abbreviation]

            for bucket,data in wrc_buckets.items():
                team_row.append(f"{data['plate_appearances']}")
                # print(f"{team} {bucket}")
                # print(f"\tplate appearances: {data['plate_appearances']}")
                # print(f"\tpositions: {data['positions']}")
                # print(f"\tplayers: {data['num_players']}")
                # # print(f"\tplayers: {', '.join(data['players'])}")

            print(",".join(team_row))
