# ABOUTME: Management command to blank MLB and AAA roster flags.
# ABOUTME: Sets is_ulmg_mlb_roster and is_ulmg_aaa_roster to False for all players.

from django.core.management.base import BaseCommand

from ulmg import models, utils


class Command(BaseCommand):
    help = "Blank MLB and AAA roster flags for all players (Player and PlayerStatSeason)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be updated without making changes.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        current_season = utils.get_current_season()

        if dry_run:
            player_mlb = models.Player.objects.filter(is_ulmg_mlb_roster=True).count()
            player_aaa = models.Player.objects.filter(is_ulmg_aaa_roster=True).count()
            pss_mlb = models.PlayerStatSeason.objects.filter(
                season=current_season, is_ulmg_mlb_roster=True
            ).count()
            pss_aaa = models.PlayerStatSeason.objects.filter(
                season=current_season, is_ulmg_aaa_roster=True
            ).count()
            self.stdout.write(
                f"Would blank: Player MLB={player_mlb}, AAA={player_aaa}; "
                f"PlayerStatSeason MLB={pss_mlb}, AAA={pss_aaa}"
            )
            return

        models.Player.objects.filter(is_ulmg_mlb_roster=True).update(
            is_ulmg_mlb_roster=False
        )
        models.Player.objects.filter(is_ulmg_aaa_roster=True).update(
            is_ulmg_aaa_roster=False
        )
        models.PlayerStatSeason.objects.filter(season=current_season).update(
            is_ulmg_mlb_roster=False,
            is_ulmg_aaa_roster=False,
        )
        self.stdout.write(self.style.SUCCESS("Blanked MLB and AAA rosters."))
