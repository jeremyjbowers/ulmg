from django.core.management.base import BaseCommand, CommandError
from ulmg import models

DRAFT_MAPS = {
    "offseason": {"rounds": {"aa": 5, "open": 5}},
    "midseason": {"rounds": {"open": 3, "aa": 1}},
}


class Command(BaseCommand):
    """
    django-admin generate_draft_picks 2020 midseason
    this will generate the picks without saving their order.
    you can save the order with the generate_draft_order management command.
    """

    def add_arguments(self, parser):
        parser.add_argument("year", type=str)
        parser.add_argument("season", type=str)

    def handle(self, *args, **options):
        season = options.get("season", None)
        year = options.get("year", None)

        teams = [t for t in models.Team.objects.all()]

        for o, team in enumerate(teams):
            for draft_type, rounds in DRAFT_MAPS[season]["rounds"].items():
                for r in range(0, rounds):
                    draft_round = r + 1
                    obj, created = models.DraftPick.objects.get_or_create(
                        year=year,
                        season=season,
                        draft_type=draft_type,
                        draft_round=draft_round,
                        original_team=team,
                    )
                    obj.save()
                    if created:
                        obj.team = team
                        obj.save()
                        print("+%s" % obj)
                    else:
                        print("*%s" % obj)
