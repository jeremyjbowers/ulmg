# ABOUTME: Loads Statcast park factors into Venue so the sim can score each home park.
# ABOUTME: Reads the Baseball Savant leaderboard, or a saved copy of that page with --file.

import requests
from django.core.management.base import BaseCommand, CommandError

from ulmg import utils
from ulmg.park_factors import fetch_parks, load_parks, rows_from_file


class Command(BaseCommand):
    help = "Load Statcast park factors into each MLB venue. 100 is average. A 3-year roll is the default."

    def add_arguments(self, parser):
        parser.add_argument(
            "--year",
            type=int,
            default=None,
            help="Last season in the window (defaults to the current season)",
        )
        parser.add_argument(
            "--rolling",
            type=int,
            default=3,
            choices=(1, 2, 3),
            help="How many seasons to roll together. 1 is a single season.",
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
            help="Count the parks without saving",
        )

    def handle(self, *args, **options):
        year = options["year"] if options["year"] is not None else utils.get_current_season()
        dry_run = options["dry_run"]
        try:
            if options["file"]:
                rows = rows_from_file(options["file"])
            else:
                rows = fetch_parks(year, options["rolling"])
        except (OSError, ValueError, requests.RequestException) as error:
            raise CommandError(str(error)) from error

        count = load_parks(rows, dry_run=dry_run)
        window = rows[0].get("year_range") if rows else str(year)
        verb = "Would store" if dry_run else "Stored"
        noun = "park" if count == 1 else "parks"
        self.stdout.write(f"{verb} {count} {noun} for {window}.")
