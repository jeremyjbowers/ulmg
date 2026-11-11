# ABOUTME: Files a test 30-man for every team, or blanks MLB and AAA flags with --reset.
# ABOUTME: A shell command for playtesting. It does not add anything to the site.
from django.conf import settings
from django.core.management.base import BaseCommand

from ulmg import models, plans, roster_moves, roster_seed


def _count(count, word):
    return f"{count} {word}" if count == 1 else f"{count} {word}s"


class Command(BaseCommand):
    help = (
        "File a test 30-man on every team, or blank every MLB and AAA flag with --reset. "
        "Not shown on the site."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--season",
            type=int,
            default=None,
            help=f"ULMG season. Defaults to {settings.CURRENT_SEASON}.",
        )
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Set every MLB and AAA flag to false, on players and on that season's stat lines.",
        )
        parser.add_argument("--dry-run", action="store_true", help="Print the roster or the blank, then change nothing.")

    def handle(self, *args, **options):
        season = settings.CURRENT_SEASON if options["season"] is None else options["season"]
        if options["reset"]:
            self.reset(season, options["dry_run"])
            return
        self.file(season, options["dry_run"])

    def file(self, season, dry_run):
        started = [half for half in (1, 2) if roster_moves.half_has_started(season, half)]
        if started:
            halves = " and ".join(str(half) for half in started)
            self.stdout.write(self.style.WARNING(
                f"Half {halves} of {season} has started. "
                "Home rosters stay on the opening snapshot until reset_sim_season."
            ))
        size = settings.MLB_ROSTER_SIZE
        for team in models.Team.objects.order_by("abbreviation"):
            players = list(models.Player.objects.filter(team=team).order_by("id"))
            chosen = roster_seed.choose(players, season, size)
            if not dry_run:
                roster_seed.write_team(team, chosen, season)
            pitchers = sum(1 for player in chosen if plans.can_pitch(player))
            hitters = len(chosen) - pitchers
            line = (
                f"{team.abbreviation} {len(chosen)}/{size} "
                f"({_count(pitchers, 'pitcher')}, {_count(hitters, 'hitter')})"
            )
            if len(chosen) < size:
                line += f"; {size - len(chosen)} short"
            self.stdout.write(("Would file " if dry_run else "Filed ") + line)

    def reset(self, season, dry_run):
        if dry_run:
            players, stats = roster_seed.blank_counts(season)
            self.stdout.write(f"Would blank {players} players and {stats} stat lines.")
            return
        players, stats = roster_seed.blank(season)
        self.stdout.write(self.style.SUCCESS(
            f"Blanked MLB and AAA rosters: {players} players, {stats} stat lines."
        ))
