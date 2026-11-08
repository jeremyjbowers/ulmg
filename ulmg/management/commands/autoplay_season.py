# ABOUTME: Autoplays a ULMG season's unplayed sim games in day order, one game per transaction, printing each final.
# ABOUTME: --team and --games narrow it, --dry-run lists the games; it stops cleanly when a game pauses for a pitcher.

import time

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q

from ulmg import autoplay, models, schedule, sim_game


def label(game):
    return f"Day {game.day}: {game.series.road_team.abbreviation} at {game.series.home_team.abbreviation}"


class Command(BaseCommand):
    help = "Autoplay a ULMG season's unplayed sim games in day order, with the computer holding every seat."

    def add_arguments(self, parser):
        parser.add_argument("--season", type=int, required=True, help="ULMG season, e.g. 2026")
        parser.add_argument("--team", default=None, help="Only this team's games, home and road, by abbreviation")
        parser.add_argument("--games", type=int, default=None, help="Autoplay at most this many games")
        parser.add_argument("--dry-run", action="store_true", help="List the games it would autoplay; play nothing")

    def games(self, season, team):
        games = (
            schedule.season_games(season)
            .filter(Q(home_score__isnull=True) | Q(road_score__isnull=True))
            .select_related("series__slot", "series__home_team", "series__road_team")
            .order_by("day", "series__home_team__abbreviation")
        )
        if team is not None:
            games = games.filter(Q(series__home_team=team) | Q(series__road_team=team))
        return games

    def handle(self, *args, **options):
        season = options["season"]
        team = None
        if options["team"]:
            team = models.Team.objects.filter(abbreviation__iexact=options["team"]).first()
            if team is None:
                raise CommandError(f"No team has the abbreviation {options['team']}.")
        games = self.games(season, team)
        if options["games"] is not None:
            games = games[: options["games"]]

        if options["dry_run"]:
            count = 0
            for game in games:
                count += 1
                state = "in progress" if sim_game.has_log(game) else "unopened"
                self.stdout.write(f"{label(game)} ({state})")
            self.stdout.write(self.style.WARNING(f"Dry run: would autoplay {count} game{'s' if count != 1 else ''}."))
            return

        played = 0
        for game in games:
            started = time.monotonic()
            try:
                result = autoplay.autoplay_game(game, None)
            except sim_game.GameRefused as refused:
                raise CommandError(f"{label(game)} can't be autoplayed. " + " ".join(refused.reasons))
            elapsed = time.monotonic() - started
            if not result.final:
                self.stdout.write(
                    f"{label(game)} paused after {result.plate_appearances} plate appearances: "
                    f"{result.paused['reason']}"
                )
                self.stdout.write(
                    self.style.WARNING(
                        f"Stopped after autoplaying {played} game{'s' if played != 1 else ''}. A roster move or a "
                        "usage override resumes the paused game; run the command again after."
                    )
                )
                return
            played += 1
            final = result.log.events.filter(kind=models.GameEvent.FINAL).first()
            self.stdout.write(
                f"{label(game)} final. {final.text} "
                f"({result.plate_appearances} plate appearances, {elapsed:.1f}s)"
            )
        self.stdout.write(self.style.SUCCESS(f"Autoplayed {played} game{'s' if played != 1 else ''}."))
