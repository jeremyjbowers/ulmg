# ABOUTME: Loads Statcast sprint speed onto the season's 1-mlb hitting lines.
# ABOUTME: Reads the Baseball Savant leaderboard, or a saved copy of that page with --file.

import requests
from django.core.management.base import BaseCommand, CommandError

from ulmg import utils
from ulmg.sprint_speed import fetch_runners, load_sprint_speeds, rows_from_file


def _lines(count):
    noun = "hitting line" if count == 1 else "hitting lines"
    return f"{count} {noun}"


def _no_line(count):
    noun = "player" if count == 1 else "players"
    return f"{count} {noun} had no 1-mlb hitting line."


def _missing(count):
    if count == 1:
        return "1 runner was not in the league."
    return f"{count} runners were not in the league."


class Command(BaseCommand):
    help = (
        "Load Statcast sprint speed onto each 1-mlb hitting line. "
        "Run after FanGraphs stats. Cards combine it with FanGraphs BsR."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--year",
            type=int,
            default=None,
            help="Season to load (defaults to the current MLB season)",
        )
        parser.add_argument(
            "--min",
            type=int,
            default=5,
            help="Minimum competitive runs on the Savant board",
        )
        parser.add_argument(
            "--file",
            type=str,
            default=None,
            help="Read a saved leaderboard page (.html) or JSON list instead of Baseball Savant",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Count the runners without saving",
        )

    def handle(self, *args, **options):
        year = options["year"] if options["year"] is not None else utils.get_current_season()
        dry_run = options["dry_run"]
        try:
            if options["file"]:
                rows = rows_from_file(options["file"])
            else:
                rows = fetch_runners(year, options["min"])
        except (OSError, ValueError, requests.RequestException) as error:
            raise CommandError(str(error)) from error

        result = load_sprint_speeds(rows, year, dry_run=dry_run)
        verb = "Would store" if dry_run else "Stored"
        self.stdout.write(
            f"{verb} sprint speed on {_lines(result['lines'])} for {year}. "
            f"{_no_line(result['no_line'])} {_missing(result['missing'])}"
        )
