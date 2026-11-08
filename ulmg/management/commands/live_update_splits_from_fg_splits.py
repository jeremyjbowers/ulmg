# ABOUTME: Stores FanGraphs platoon splits on each player's 1-mlb PlayerStatSeason.split_stats, keyed by split.
# ABOUTME: Reads the S3 copies written by live_download_fg_splits (or --dir) and processes keys like the stats loader.
import json
import os
from collections import defaultdict

import requests
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from ulmg import models
from ulmg.management.commands.live_download_fg_splits import SPLITS, splits_local_path
from ulmg.management.commands.live_update_stats_from_fg_stats import Command as FgStatsCommand

# FanGraphs columns the card reads from each split row, by splits-tool position.
REQUIRED_COLUMNS = {
    "B": ["PA", "SO", "BB", "HBP", "1B", "2B", "3B", "HR"],
    "P": ["TBF", "SO", "BB", "HBP", "H", "HR"],
}


class Command(BaseCommand):
    """
        Split rows are the splits tool's standard (strType 1) player lines. Cards read PA, SO, BB, HBP,
        1B, 2B, 3B and HR from hitter splits and TBF, SO, BB, HBP, H and HR from pitcher splits,
        the same columns the overall card reads from the leaderboards. Rows are matched on
        'playerid' (FanGraphs id), then 'xMLBAMID' when a row carries it.
    """

    help = 'Store a season of FanGraphs platoon splits on 1-mlb PlayerStatSeason records'

    def add_arguments(self, parser):
        parser.add_argument(
            '--season',
            type=int,
            default=None,
            help='Season to load (defaults to the card season, CURRENT_SEASON - 1)',
        )
        parser.add_argument(
            '--dir',
            type=str,
            default=None,
            help='Read the fg_mlb_splits_*.json files from this local directory instead of S3',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be stored without saving',
        )

    def get_rows(self, season, key, directory):
        filename = os.path.basename(splits_local_path(season, key))
        if directory:
            with open(os.path.join(directory, filename)) as readfile:
                return json.load(readfile)
        url = f"https://static-theulmg.nyc3.digitaloceanspaces.com/fg-stats/{season}/{filename}"
        return requests.get(url).json()

    def check_columns(self, key, position, rows):
        """Fail before saving anything when the split rows lack a column the card needs."""
        for row in rows:
            missing = [column for column in REQUIRED_COLUMNS[position] if column not in row]
            if missing:
                raise CommandError(
                    f"FanGraphs {key} rows are missing {', '.join(missing)}; "
                    f"a row has columns {', '.join(sorted(row.keys()))}"
                )

    def find_player(self, row):
        fg_id = row.get('playerid')
        mlbam_id = row.get('xMLBAMID')
        if fg_id:
            player = models.Player.objects.filter(fg_id=fg_id).first()
            if player:
                return player
        if mlbam_id:
            return models.Player.objects.filter(mlbam_id=mlbam_id).first()
        return None

    def handle(self, *args, **options):
        season = options.get('season') or settings.CURRENT_SEASON - 1
        dry_run = options.get('dry_run', False)
        stats_command = FgStatsCommand()

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN: no splits will be saved"))

        by_player = defaultdict(dict)
        first_rows = {}
        for key, (position, _split_id) in SPLITS.items():
            rows = self.get_rows(season, key, options.get('dir'))
            self.check_columns(key, position, rows)
            self.stdout.write(f"Read {len(rows)} FanGraphs {key} rows for {season}")
            for row in rows:
                player_key = row.get('playerid') or row.get('xMLBAMID')
                if not player_key:
                    continue
                first_rows.setdefault(player_key, row)
                by_player[player_key][key] = {
                    stats_command._process_k(k): stats_command._process_v(k, v) for k, v in row.items()
                }

        updated = 0
        total = len(by_player)
        for idx, (player_key, split_stats) in enumerate(by_player.items(), start=1):
            player = self.find_player(first_rows[player_key])
            if not player:
                continue

            pss = models.PlayerStatSeason.objects.filter(
                player=player, season=season, classification="1-mlb", is_career=False
            ).first()
            if not pss:
                continue

            pss.split_stats = split_stats
            if not dry_run:
                pss.save()
            updated += 1
            self.stdout.write(f"[{idx}/{total}] {player}: {', '.join(sorted(split_stats))}")

        self.stdout.write(self.style.SUCCESS(f"Updated splits for {updated} players"))
