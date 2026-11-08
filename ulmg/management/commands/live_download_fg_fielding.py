# ABOUTME: Downloads the FanGraphs major-league fielding leaderboard (one row per player per position) for a season.
# ABOUTME: Saves data/{season}/fg_mlb_fld.json and uploads it to S3 like live_download_fg_stats.
import json
import os

import urllib3
from django.conf import settings
from django.core.management.base import BaseCommand

from ulmg import utils

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class Command(BaseCommand):
    help = 'Download a season of the FanGraphs fielding leaderboard and save both locally and to S3'

    def add_arguments(self, parser):
        parser.add_argument(
            '--season',
            type=int,
            default=None,
            help='Season to download (defaults to the card season, CURRENT_SEASON - 1)',
        )
        parser.add_argument(
            '--local-only',
            action='store_true',
            help='Save files locally only, skip S3 upload'
        )

    def fielding_url(self, season):
        return (
            "https://www.fangraphs.com/api/leaders/major-league/data"
            f"?age=&pos=all&stats=fld&lg=all&qual=0&season={season}&season1={season}"
            "&startdate=&enddate=&month=0&hand=&team=0&pageitems=10000&pagenum=1"
            "&ind=0&rost=0&players=&type=1&postseason=&sortdir=default&sortstat=Defense"
        )

    def handle(self, *args, **options):
        season = options.get('season') or settings.CURRENT_SEASON - 1
        local_only = options.get('local_only', False)

        if not local_only and not utils.s3_manager.s3_client:
            self.stdout.write(self.style.WARNING("S3 not configured, saving locally only"))
            local_only = True

        self.stdout.write(f"Downloading FanGraphs fielding leaderboard for {season}...")
        rows = utils.fg_get(self.fielding_url(season), verify=False).json()['data']

        local_path = f'data/{season}/fg_mlb_fld.json'
        if local_only:
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            with open(local_path, 'w') as writefile:
                json.dump(rows, writefile, indent=2)
            self.stdout.write(f"Saved {len(rows)} MLB fielding rows to {local_path}")
        else:
            utils.s3_manager.save_and_upload_json(rows, local_path)
            self.stdout.write(f"Saved {len(rows)} MLB fielding rows to {local_path} and uploaded to S3")
