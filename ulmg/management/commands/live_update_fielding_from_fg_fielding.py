# ABOUTME: Stores the FanGraphs fielding leaderboard on each player's 1-mlb PlayerStatSeason, keyed by position.
# ABOUTME: Reads the S3 copy written by live_download_fg_fielding (or --file) and processes keys like the stats loader.
import json
from collections import defaultdict

import requests
from django.conf import settings
from django.core.management.base import BaseCommand

from ulmg import models, utils
from ulmg.management.commands.live_update_stats_from_fg_stats import Command as FgStatsCommand


class Command(BaseCommand):
    """
        mlb fld dict_keys(['Season', 'Name', 'Team', 'xMLBAMID', 'PlayerNameRoute', 'PlayerName', 'playerid', 'SeasonMin', 'SeasonMax', 'Pos', 'Position', 'G', 'GS', 'Inn', 'PO', 'A', 'E', 'FE', 'TE', 'DP', 'DPS', 'DPT', 'DPF', 'SB', 'CS', 'PB', 'WP', 'FP', 'rSB', 'rGFP', 'rSZ', 'rCERA', 'DRS', 'Defense', 'CStrikes', 'CFraming', 'dFRP', 'bFRP', 'tFRP', 'fFRP', 'FRP', 'Q', 'TInn', 'positionDB', 'teamid', 'TeamName', 'TeamNameAbb', 'playerTeamId', 'rGDP', 'rPM', 'BIZ', 'Plays', 'RZR', 'OOZ', 'DPR', 'RngR', 'ErrR', 'UZR', 'UZR/150', 'OAA', 'rFRP', 'aFRP', 'rARM', 'ARM', 'Scp'])

        Cards read 'Inn' (innings, FanGraphs whole.outs notation) and 'FRP' (fielding runs, without the
        positional adjustment) from each position row. 'Defense' is FanGraphs Def for that row.
    """

    help = 'Store a season of FanGraphs fielding rows on 1-mlb PlayerStatSeason records'

    def add_arguments(self, parser):
        parser.add_argument(
            '--season',
            type=int,
            default=None,
            help='Season to load (defaults to the card season, CURRENT_SEASON - 1)',
        )
        parser.add_argument(
            '--file',
            type=str,
            default=None,
            help='Read the leaderboard from a local JSON file instead of S3',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be stored without saving',
        )

    def get_rows(self, season, path):
        if path:
            with open(path) as readfile:
                return json.load(readfile)
        url = f"https://static-theulmg.nyc3.digitaloceanspaces.com/fg-stats/{season}/fg_mlb_fld.json"
        return requests.get(url).json()

    def find_players(self, row, dry_run):
        """Every player this row belongs to, including one still stored under a minor-league FanGraphs id."""
        players = utils.players_for_fangraphs_row(row.get('playerid'), row.get('xMLBAMID'), row.get('PlayerName'))
        if not dry_run:
            for player in players:
                utils.remember_fangraphs_ids(player, row.get('playerid'), row.get('xMLBAMID'))
        return players

    def handle(self, *args, **options):
        season = options.get('season') or settings.CURRENT_SEASON - 1
        dry_run = options.get('dry_run', False)
        stats_command = FgStatsCommand()

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN: no fielding will be saved"))

        rows = self.get_rows(season, options.get('file'))
        self.stdout.write(f"Read {len(rows)} FanGraphs fielding rows for {season}")

        by_player = defaultdict(list)
        for row in rows:
            key = row.get('playerid') or row.get('xMLBAMID')
            if key:
                by_player[key].append(row)

        updated = 0
        total = len(by_player)
        for idx, player_rows in enumerate(by_player.values(), start=1):
            players = self.find_players(player_rows[0], dry_run)
            if not players:
                continue

            for player in players:
                pss = models.PlayerStatSeason.objects.filter(
                    player=player, season=season, classification="1-mlb", is_career=False
                ).first()
                if not pss:
                    continue

                fielding_stats = {}
                for row in player_rows:
                    stat_dict = {stats_command._process_k(k): v for k, v in row.items()}
                    position = stat_dict.get('pos')
                    if not position:
                        continue
                    if position in fielding_stats:
                        self.stdout.write(self.style.WARNING(
                            f"{player} has more than one {position} row; check that 'Pos' is the row's position"
                        ))
                    fielding_stats[position] = stat_dict

                pss.fielding_stats = fielding_stats
                if not dry_run:
                    pss.save()
                updated += 1
                self.stdout.write(f"[{idx}/{total}] {player}: {', '.join(sorted(fielding_stats))}")

        self.stdout.write(self.style.SUCCESS(f"Updated fielding for {updated} players"))
