# ABOUTME: Summarizes team pitching depth by xFIP/SIERA threshold buckets.
# ABOUTME: Outputs CSV tables for innings pitched and game starts per team.
from django.core.management.base import BaseCommand

from ulmg import models, utils


METRIC_FIELDS = {
    "xfip": "xfip",
    "siera": "siera",
    "fip": "fip",
    "era": "era",
}


class Command(BaseCommand):
    help = (
        "Summarize team pitching by metric threshold buckets. "
        "Counts owned MLB pitchers only. "
        "Prints innings pitched and game starts for pitchers below each threshold."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--metric",
            choices=METRIC_FIELDS.keys(),
            default="xfip",
            help="Pitching metric to bucket on (default: xfip). Lower is better.",
        )
        parser.add_argument(
            "--min-ip",
            type=float,
            default=5,
            help="Minimum MLB innings pitched to qualify (default: 5).",
        )

    def handle(self, *args, **options):
        metric = options["metric"]
        metric_field = METRIC_FIELDS[metric]
        min_ip = options["min_ip"]
        thresholds = [3, 3.5, 4]
        season = utils.get_current_season()
        teams = models.Team.objects.all().order_by("abbreviation")

        threshold_labels = [f"<{threshold}" for threshold in thresholds]

        self._print_table(
            label="innings_pitched",
            teams=teams,
            season=season,
            metric_field=metric_field,
            min_ip=min_ip,
            thresholds=thresholds,
            threshold_labels=threshold_labels,
            stat_key="ip",
        )
        self._print_table(
            label="starts",
            teams=teams,
            season=season,
            metric_field=metric_field,
            min_ip=min_ip,
            thresholds=thresholds,
            threshold_labels=threshold_labels,
            stat_key="gs",
        )

    def _print_table(
        self,
        label,
        teams,
        season,
        metric_field,
        min_ip,
        thresholds,
        threshold_labels,
        stat_key,
    ):
        print(f"{label},team,{','.join(threshold_labels)}")

        for team in teams:
            bucket_totals = {threshold: 0 for threshold in thresholds}

            for threshold in thresholds:
                qualifying_stat_seasons = models.PlayerStatSeason.objects.filter(
                    player__team=team,
                    season=season,
                    classification="1-mlb",
                    is_career=False,
                    player__position__icontains="P",
                    pitch_stats__ip__gte=min_ip,
                    **{f"pitch_stats__{metric_field}__lt": threshold},
                ).select_related("player")

                for stat_season in qualifying_stat_seasons:
                    pitch_stats = stat_season.pitch_stats or {}
                    bucket_totals[threshold] += pitch_stats.get(stat_key, 0) or 0

            team_row = [team.abbreviation] + [
                str(bucket_totals[threshold]) for threshold in thresholds
            ]
            print(",".join(team_row))
