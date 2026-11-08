# ABOUTME: Resets one season's simulation data from the ulmg.sim_data registry, leaving real league data alone.
# ABOUTME: A dry run unless --confirm repeats the season; --include-schedule also deletes the schedule.

from django.core.management.base import BaseCommand, CommandError

from ulmg import sim_data


class Command(BaseCommand):
    help = (
        "Reset a season's sim data: game results, the usage ledger and 6-ulmg season lines. "
        "Dry run unless --confirm repeats the season."
    )

    def add_arguments(self, parser):
        parser.add_argument("--season", type=int, required=True, help="ULMG season, e.g. 2027")
        parser.add_argument(
            "--confirm",
            type=int,
            default=None,
            help="Repeat the season number to delete. Without it, nothing changes.",
        )
        parser.add_argument(
            "--include-schedule",
            action="store_true",
            help="Also delete the season's schedule so generate_schedule can run again",
        )

    def handle(self, *args, **options):
        season = options["season"]
        confirm = options["confirm"]
        include_schedule = options["include_schedule"]

        if confirm is not None and confirm != season:
            raise CommandError(
                f"--confirm {confirm} does not match --season {season}; nothing changed."
            )

        if confirm is None:
            steps = sim_data.plan_reset(season, include_schedule=include_schedule)
            self.stdout.write(self.style.WARNING(f"Dry run: pass --confirm {season} to reset {season}"))
            for index, step in enumerate(steps, start=1):
                self.stdout.write(f"{index}/{len(steps)} {step.describe(done=False)}")
            self.stdout.write(
                self.style.WARNING(sim_data.summarize(season, steps, include_schedule, done=False))
            )
            return

        try:
            steps = sim_data.reset_season(
                season, include_schedule=include_schedule, progress=self.stdout.write
            )
        except sim_data.SimResetError as error:
            raise CommandError(str(error))
        self.stdout.write(self.style.SUCCESS(sim_data.summarize(season, steps, include_schedule, done=True)))
