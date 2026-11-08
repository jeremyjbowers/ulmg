# ABOUTME: Builds a playable test season in one step: draws the schedule with generate_schedule and fills every team's half plan.
# ABOUTME: Plans use the test-setup defaults in ulmg.sim_setup; --both-halves (testing only) also fills the second half early.
import secrets
from io import StringIO

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from ulmg import models, schedule, sim_setup


class DryRunRollback(Exception):
    """Raised inside the setup transaction to undo a dry run."""


class Command(BaseCommand):
    help = (
        "Set up a sim test season: generate the schedule and fill every team's first-half plan "
        "from its 30-man with test-setup defaults."
    )

    def add_arguments(self, parser):
        parser.add_argument("--season", type=int, required=True, help="Season year, e.g. 2027")
        parser.add_argument(
            "--seed",
            type=int,
            default=None,
            help="Seed for a reproducible schedule draw. A random seed is drawn and reported if omitted.",
        )
        parser.add_argument(
            "--both-halves",
            action="store_true",
            help=(
                "Testing only: also fill the second-half plan, ignoring TEAM_SEASON_HALF. "
                "The plan pages keep the second half locked until the trade break."
            ),
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Run the whole setup, print the summary, then roll everything back",
        )

    def handle(self, *args, **options):
        season = options["season"]
        seed = options["seed"]
        if seed is None:
            seed = secrets.randbelow(2**31)
        halves = (1, 2) if options["both_halves"] else (1,)

        if schedule.season_has_played_games(season):
            raise CommandError(
                f"{season} has played games; its schedule can no longer be regenerated. "
                f"Run reset_sim_season --season {season} --include-schedule first."
            )

        self.stdout.write(f"Season: {season}")
        self.stdout.write(f"Seed: {seed}")
        try:
            with transaction.atomic():
                call_command(
                    "generate_schedule", "--season", str(season), "--seed", str(seed), stdout=StringIO()
                )
                self.stdout.write("Schedule drawn; filling plans")
                results = sim_setup.fill_season_plans(season, halves)
                self.summarize(season, halves, results)
                if options["dry_run"]:
                    raise DryRunRollback()
        except DryRunRollback:
            self.stdout.write(self.style.WARNING("Dry run: nothing saved"))

    def summarize(self, season, halves, results):
        teams = models.Team.objects.all()
        per_team = {len(schedule.team_games(team, season)) for team in teams}
        per_team_text = ", ".join(str(n) for n in sorted(per_team))
        self.stdout.write(
            f"Games created: {schedule.season_games(season).count()} ({per_team_text} per team)"
        )

        plan_count = len(results) * len(halves)
        complete = sum(
            1
            for _, by_half, problems in results
            for half in halves
            if not problems and not by_half[half]
        )
        half_text = "half 1" if halves == (1,) else "halves 1 and 2"
        self.stdout.write(f"Plans filled: {plan_count} for {half_text} ({complete} complete)")

        troubled = [
            (team, problems, by_half)
            for team, by_half, problems in results
            if problems or any(by_half.values())
        ]
        if not troubled:
            self.stdout.write(self.style.SUCCESS("Teams with problems: none"))
            return
        self.stdout.write(self.style.WARNING(f"Teams with problems: {len(troubled)}"))
        for team, problems, by_half in troubled:
            for problem in problems:
                self.stdout.write(f"  {team.abbreviation}: {problem}")
            for half, half_problems in by_half.items():
                for problem in half_problems:
                    self.stdout.write(f"  {team.abbreviation}: Half {half}: {problem}")
