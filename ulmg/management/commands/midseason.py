# ABOUTME: Post-midseason Open Draft transition: reset rosters and place picks on MLB.
# ABOUTME: Promotes 1H protections and marks midseason Open picks as 2H draft / MLB.

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db.models import Q

from ulmg import models
from ulmg.views.api import update_player_stat_season_roster


class Command(BaseCommand):
    help = (
        "Run AFTER the midseason Open Draft. Clears MLB/AAA rosters, promotes "
        "1H protections to MLB, and places midseason Open picks on MLB with "
        "is_ulmg_2h_draft."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would change without writing to the database.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        year = str(settings.CURRENT_SEASON)

        open_picks = models.DraftPick.objects.filter(
            year=year, season="midseason", draft_type="open"
        ).exclude(player__isnull=True)
        one_h_count = models.Player.objects.filter(
            Q(is_ulmg_1h_c=True) | Q(is_ulmg_1h_p=True) | Q(is_ulmg_1h_pos=True)
        ).count()
        current_mlb = models.Player.objects.filter(is_ulmg_mlb_roster=True).count()
        current_aaa = models.Player.objects.filter(is_ulmg_aaa_roster=True).count()

        self.stdout.write(
            f"Midseason transition for {year}: "
            f"{open_picks.count()} Open picks with players, "
            f"{one_h_count} 1H-protected, "
            f"{current_mlb} currently MLB, {current_aaa} currently AAA"
        )

        if dry_run:
            self.stdout.write("Would clear all MLB/AAA roster flags")
            self.stdout.write(f"Would promote {one_h_count} 1H-protected players to MLB")
            self.stdout.write(
                f"Would mark {open_picks.count()} midseason Open picks as "
                "is_ulmg_2h_draft + MLB roster"
            )
            for pick in open_picks.select_related("player", "team")[:20]:
                self.stdout.write(
                    f"  pick R{pick.draft_round}.{pick.pick_number} "
                    f"{pick.player.name} -> {pick.team.abbreviation} MLB/2H draft"
                )
            if open_picks.count() > 20:
                self.stdout.write(f"  ... and {open_picks.count() - 20} more")
            return

        # DO NOT RUN THIS UNTIL AFTER THE DRAFT IS OVER
        models.Player.objects.filter(is_ulmg_2h_draft=True).update(is_ulmg_2h_draft=False)
        models.Player.objects.filter(is_ulmg_mlb_roster=True).update(is_ulmg_mlb_roster=False)
        models.Player.objects.filter(is_ulmg_aaa_roster=True).update(is_ulmg_aaa_roster=False)
        models.PlayerStatSeason.objects.filter(season=settings.CURRENT_SEASON).update(
            is_ulmg_mlb_roster=False,
            is_ulmg_aaa_roster=False,
        )

        models.Player.objects.filter(is_ulmg_1h_c=True).update(
            is_ulmg_mlb_roster=True, is_ulmg_protected=True
        )
        models.Player.objects.filter(is_ulmg_1h_p=True).update(
            is_ulmg_mlb_roster=True, is_ulmg_protected=True
        )
        models.Player.objects.filter(is_ulmg_1h_pos=True).update(
            is_ulmg_mlb_roster=True, is_ulmg_protected=True
        )
        models.Player.objects.filter(is_ulmg_reserve=True).update(is_ulmg_protected=True)

        for player in models.Player.objects.filter(is_ulmg_mlb_roster=True):
            update_player_stat_season_roster(
                player,
                is_ulmg_mlb_roster=True,
                is_ulmg_aaa_roster=False,
                owned=True,
            )

        marked = 0
        for pick in open_picks.select_related("player", "team"):
            player = pick.player
            player.is_ulmg_2h_draft = True
            player.is_ulmg_mlb_roster = True
            player.is_ulmg_aaa_roster = False
            if pick.team_id and player.team_id != pick.team_id:
                player.team = pick.team
            player.save()
            update_player_stat_season_roster(
                player,
                is_ulmg_mlb_roster=True,
                is_ulmg_aaa_roster=False,
                owned=True,
            )
            marked += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Midseason transition complete: marked {marked} Open picks on MLB/2H draft"
            )
        )
