from django.core.management.base import BaseCommand, CommandError
from ulmg import models

DRAFT_MAPS = {
    'offseason': {
        "rounds": {
            "aa": 5,
            "open": 5
        }
    },
    'midseason': {
        "rounds": {
            "open": 3,
            # "aa": 1
        }
    }
}

class Command(BaseCommand):
    """
    AA_TYPE = "aa"
    OPEN_TYPE = "open"
    BALANCE_TYPE = "balance"
    DRAFT_TYPE_CHOICES = (
        (AA_TYPE,"aa"),
        (OPEN_TYPE,"open"),
        (BALANCE_TYPE,"balance"),
    )
    draft_type = models.CharField(max_length=255, choices=DRAFT_TYPE_CHOICES, null=True)
    draft_round = models.IntegerField(null=True)
    year = models.CharField(max_length=4)
    pick_number = models.IntegerField()
    OFFSEASON = "offseason"
    MIDSEASON = "midseason"
    SEASON_CHOICES = (
        (OFFSEASON,"offseason"),
        (MIDSEASON,"midseason"),
    )
    season = models.CharField(max_length=255, choices=SEASON_CHOICES)
    team = models.ForeignKey(Team, on_delete=models.SET_NULL, blank=True, null=True)
    team_name = models.CharField(max_length=255, blank=True, null=True)
    player = models.ForeignKey(Player, on_delete=models.SET_NULL, blank=True, null=True)
    player_name = models.CharField(max_length=255, blank=True, null=True)
    pick_notes = models.TextField(blank=True, null=True)
    """

    def add_arguments(self, parser):
        parser.add_argument('year', type=str)
        parser.add_argument('season', type=str)
        parser.add_argument('draft_order_filepath', type=str)

    def handle(self, *args, **options):
        season = options.get('season', None)
        year = options.get('year', None)
        draft_order_filepath = options.get('draft_order_filepath', None)

        with open(draft_order_filepath, 'r') as readfile:
            order = [n for n in readfile.read().split('\n') if n != ""]

            for o, t in enumerate(order):
                team = models.Team.objects.get(abbreviation=t)
                for draft_type,rounds in DRAFT_MAPS[season]['rounds'].items():
                    for r in range(0,rounds):
                        draft_round = r+1
                        try:
                            obj = models.DraftPick.objects.get(
                                year=year,
                                season=season,
                                draft_type=draft_type,
                                draft_round=draft_round,
                                original_team=team,
                            )
                            obj.pick_number = o+1
                            obj.save()
                            print("*%s" % obj)
                        except:
                            print(year, season, draft_type, draft_round, team)