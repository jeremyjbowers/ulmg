from django.core.management.base import BaseCommand, CommandError
from ulmg import models

DRAFT_MAPS = {"offseason": {"aa": 5, "open": 5}, "midseason": {"open": 3, "aa": 1}}


class Command(BaseCommand):
    """
    django-admin generate_draft_order 2020 midseason aa data/ulmg/2020-midseason-aa-order.txt
    this relies on picks having been created with the generate_draft_picks management command.
    this command simply adds pick order to existing picks. helps with midseason drafts.
    also lets us assign picks years in advance (helpful for trades).
    """

    def add_arguments(self, parser):
        parser.add_argument("year", type=str)
        parser.add_argument("season", type=str)
        parser.add_argument("draft_type", type=str)
        parser.add_argument("draft_order_filepath", type=str)

    def handle(self, *args, **options):
        season = options.get("season", None)
        year = options.get("year", None)
        draft_type = options.get("draft_type", None)
        draft_order_filepath = options.get("draft_order_filepath", None)

        with open(draft_order_filepath, "r") as readfile:
            order = [n for n in readfile.read().split("\n") if n != ""]
            for o, t in enumerate(order):
                team = models.Team.objects.get(abbreviation=t)
                for r in range(0, DRAFT_MAPS[season][draft_type]):
                    draft_round = r + 1
                    try:
                        obj = models.DraftPick.objects.get(
                            year=year,
                            season=season,
                            draft_type=draft_type,
                            draft_round=draft_round,
                            original_team=team,
                        )
                        obj.pick_number = o + 1
                        obj.save()
                        print("*%s" % obj)
                    except:
                        print(year, season, draft_type, draft_round, team)
