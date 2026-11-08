# ABOUTME: Generates engine cards for every player with a 1-mlb PlayerStatSeason in the card season.
# ABOUTME: Regenerating replaces the player's card for that season; --dry-run computes without saving.
from django.conf import settings
from django.core.management.base import BaseCommand

from ulmg import cards, models


class Command(BaseCommand):
    help = 'Generate engine cards from a season of MLB stats (defaults to CURRENT_SEASON - 1)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--season',
            type=int,
            default=None,
            help='Card season (defaults to CURRENT_SEASON - 1)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Compute cards without saving them',
        )

    def card_fields(self, pss, career_pitch_stats):
        fields = {
            "plate_appearances": None,
            "wrc_plus": None,
            "hitter_rates": cards.hitter_rates(pss.hit_stats),
            "primary_position": None,
            "defense": None,
            "batters_faced": None,
            "pitcher_rates": cards.pitcher_rates(pss.pitch_stats),
            "fatigue": None,
        }

        if fields["hitter_rates"]:
            fielding = cards.fielding_from_stats(pss.fielding_stats)
            fields["plate_appearances"] = int(pss.hit_stats.get("pa"))
            fields["wrc_plus"] = pss.hit_stats.get("wrc_plus")
            fields["primary_position"] = cards.primary_position(fielding) or "DH"
            fields["defense"] = cards.defense_ratings(fielding)

        if fields["pitcher_rates"]:
            fields["batters_faced"] = int(pss.pitch_stats.get("tbf"))
            fields["fatigue"] = cards.fatigue_profile(pss.pitch_stats, career_pitch_stats)

        return fields

    def handle(self, *args, **options):
        season = options.get('season') or settings.CURRENT_SEASON - 1
        dry_run = options.get('dry_run', False)

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN: no cards will be saved"))

        stat_seasons = list(
            models.PlayerStatSeason.objects.filter(
                season=season, classification="1-mlb", is_career=False, player__isnull=False
            ).select_related("player").order_by("player__name")
        )
        career_pitching = dict(
            models.PlayerStatSeason.objects.filter(
                classification="1-mlb", is_career=True, player__in=[pss.player for pss in stat_seasons]
            ).values_list("player_id", "pitch_stats")
        )

        total = len(stat_seasons)
        generated = 0
        self.stdout.write(f"Generating {season} cards from {total} 1-mlb stat seasons...")
        for idx, pss in enumerate(stat_seasons, start=1):
            fields = self.card_fields(pss, career_pitching.get(pss.player_id))
            if not fields["hitter_rates"] and not fields["pitcher_rates"]:
                self.stdout.write(f"[{idx}/{total}] {pss.player}: no PA or TBF, skipped")
                continue

            if not dry_run:
                models.Card.objects.update_or_create(player=pss.player, season=season, defaults=fields)
            generated += 1
            self.stdout.write(f"[{idx}/{total}] {pss.player}")

        verb = "Would generate" if dry_run else "Generated"
        self.stdout.write(self.style.SUCCESS(f"{verb} {generated} cards for {season}"))
