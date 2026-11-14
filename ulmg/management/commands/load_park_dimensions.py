# ABOUTME: Loads each MLB park's dimensions, wall heights, surface and roof onto its Venue's rules.
# ABOUTME: Reads data/parks/dimensions.json, keyed by MLB venue id, and reports parks with no matching venue.

from django.core.management.base import BaseCommand, CommandError

from ulmg import park


class Command(BaseCommand):
    help = "Write each park's dimensions from data/parks/dimensions.json onto the venue with its MLB venue id."

    def add_arguments(self, parser):
        parser.add_argument(
            "--file",
            type=str,
            default=None,
            help="Read another dimension file instead of data/parks/dimensions.json",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would be stored without saving",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        try:
            parks = park.dimension_file(options["file"])
        except (OSError, ValueError) as error:
            raise CommandError(str(error)) from error

        stored, unmatched, problems = park.load_dimensions(parks, dry_run=dry_run)
        for venue in stored:
            self.stdout.write(f"  {venue.name} ({venue.mlb_venue_id})")
        for problem in problems:
            self.stdout.write(f"  Not a park rule, left out: {problem}")
        if unmatched:
            noun = "park" if len(unmatched) == 1 else "parks"
            verb = "has" if len(unmatched) == 1 else "have"
            names = ", ".join(f"{name} ({venue_id})" for venue_id, name in unmatched)
            self.stdout.write(f"{len(unmatched)} {noun} in the file {verb} no venue with that MLB venue id: {names}")
        verb = "Would store" if dry_run else "Stored"
        noun = "park" if len(stored) == 1 else "parks"
        self.stdout.write(f"{verb} dimensions for {len(stored)} {noun}.")
