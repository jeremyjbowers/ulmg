# ABOUTME: Draws a season's schedule of 46 slots (162 games per team) and saves it.
# ABOUTME: Supports --seed for a reproducible draw and --dry-run; refuses once a game is played.
import secrets

from django.core.management.base import BaseCommand, CommandError

from ulmg import models, schedule


class Command(BaseCommand):
    help = "Generate a season's schedule: 23 slots per half, 162 games per team."

    def add_arguments(self, parser):
        parser.add_argument("--season", type=int, required=True, help="Season year, e.g. 2027")
        parser.add_argument(
            "--seed",
            type=int,
            default=None,
            help="Seed for a reproducible draw. A random seed is drawn and reported if omitted.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show the drawn schedule without saving it",
        )

    def handle(self, *args, **options):
        season = options["season"]
        seed = options["seed"]
        dry_run = options["dry_run"]
        if seed is None:
            seed = secrets.randbelow(2**31)

        if schedule.season_has_played_games(season):
            raise CommandError(
                f"{season} has played games; its schedule can no longer be regenerated."
            )

        try:
            plan = schedule.build_season_plan(models.Team.objects.all(), seed)
        except schedule.ScheduleError as error:
            raise CommandError(str(error))

        self.stdout.write(f"Season: {season}")
        self.stdout.write(f"Seed: {seed}")
        slot_type_names = dict(models.ScheduleSlot.SLOT_TYPE_CHOICES)
        for slot in plan:
            matchups = ", ".join(
                f"{s.road.abbreviation} at {s.home.abbreviation}" for s in slot.series
            )
            games = "game" if slot.length == 1 else "games"
            if slot.length == 1:
                span = f"day {slot.days[0]}"
            else:
                span = f"days {slot.days[0]}-{slot.days[-1]}"
            self.stdout.write(
                f"Slot {slot.number}/{len(plan)}: half {slot.half}, "
                f"{slot_type_names[slot.slot_type].lower()}, {slot.length} {games}, "
                f"{span}: {matchups}"
            )

        if dry_run:
            self.stdout.write(self.style.WARNING("Dry run: nothing saved"))
            return

        if models.ScheduleSlot.objects.filter(season=season).exists():
            self.stdout.write(self.style.WARNING(f"Replacing the existing {season} schedule"))

        try:
            slots, series, games = schedule.save_season_plan(season, plan)
        except schedule.ScheduleError as error:
            raise CommandError(str(error))

        self.stdout.write(
            self.style.SUCCESS(
                f"Saved {slots} slots, {series} series and {games} games for {season}"
            )
        )
