# ABOUTME: One-time load of the 2012-2018 draft history file into DraftPick.
# ABOUTME: Uses the 27_club_abbrev column for the club that made the pick.

from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from ulmg import draft_history


class Command(BaseCommand):
    help = (
        "Load the 2012-2018 draft history. "
        "A pick already stored for that slot is left as it is, so this can run on every deploy. "
        "Pass --replace to reload the drafts in the file."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--file",
            default=str(draft_history.HISTORY_PATH),
            help="History CSV with a 27_club_abbrev column (default: data/ulmg/draft-history.csv)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would be created without writing picks",
        )
        parser.add_argument(
            "--replace",
            action="store_true",
            help="Delete picks for each draft in the file, then load that draft again",
        )

    def handle(self, *args, **options):
        path = Path(options["file"])
        if not path.is_file():
            raise CommandError(f"No draft history file at {path}")
        try:
            result = draft_history.load_history(
                path, dry_run=options["dry_run"], replace=options["replace"]
            )
        except ValueError as error:
            raise CommandError(str(error)) from error
        self.stdout.write(draft_history.describe(result, dry_run=options["dry_run"]))
