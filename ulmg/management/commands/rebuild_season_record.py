# ABOUTME: Rebuilds a ULMG season's 6-ulmg player lines and team records from its final game logs.
# ABOUTME: --dry-run reports what would be written and deleted without changing anything.

from django.conf import settings
from django.core.management.base import BaseCommand

from ulmg import season_record


class Command(BaseCommand):
    help = "Rebuild a ULMG season's 6-ulmg lines and team records from its final game logs."

    def add_arguments(self, parser):
        parser.add_argument(
            "--season", type=int, default=None, help="ULMG season, e.g. 2026 (default: CURRENT_SEASON)"
        )
        parser.add_argument("--dry-run", action="store_true", help="Report what would change; change nothing")

    def handle(self, *args, **options):
        season = options["season"] or settings.CURRENT_SEASON
        result = season_record.rebuild_season(season, dry_run=options["dry_run"], progress=self.stdout.write)
        style = self.style.WARNING if result.dry_run else self.style.SUCCESS
        self.stdout.write(style(result.describe()))
