# ABOUTME: Downloads a season of FanGraphs platoon splits (hitters vs LHP/RHP, pitchers vs LHH/RHH) from the splits tool.
# ABOUTME: Saves data/{season}/fg_mlb_splits_{split}.json per split and uploads to S3 like live_download_fg_stats.
import json
import os

import urllib3
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from ulmg import utils

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

SPLITS_URL = "https://www.fangraphs.com/api/leaders/splits/splits-leaders"
SPLITS_REFERER = "https://www.fangraphs.com/leaders/splits-leaderboards"

# Split key -> (splits-tool position, strSplitArr id). B is batters, P is pitchers.
SPLITS = {
    "bat_vs_lhp": ("B", 1),
    "bat_vs_rhp": ("B", 2),
    "pit_vs_lhh": ("P", 5),
    "pit_vs_rhh": ("P", 6),
}


def splits_local_path(season, key):
    return f"data/{season}/fg_mlb_splits_{key}.json"


def splits_payload(season, position, split_id):
    """The splits tool's JSON body for every player's standard (counting) line in one split and season."""
    return {
        "strPlayerId": "all",
        "strSplitArr": [split_id],
        "strSplitArrPitch": [],
        "strGroup": "season",
        "strPosition": position,
        "strType": "1",
        "strStartDate": f"{season}-01-01",
        "strEndDate": f"{season}-12-31",
        "strSplitTeams": False,
        "dctFilters": [],
        "strStatType": "player",
        "strAutoPt": "false",
        "arrPlayerId": [],
    }


def rows_from_response(response):
    """
    The splits tool answers player queries with column names in "k" and rows of values in "v",
    and team queries with a "data" list of row dicts. Either becomes a list of row dicts.
    """
    if isinstance(response, dict):
        if isinstance(response.get("data"), list):
            return response["data"]
        if isinstance(response.get("k"), list) and isinstance(response.get("v"), list):
            return [dict(zip(response["k"], values)) for values in response["v"]]
    keys = sorted(response.keys()) if isinstance(response, dict) else type(response).__name__
    raise CommandError(f"Unexpected FanGraphs splits response; expected 'k'/'v' or 'data', got {keys}")


class Command(BaseCommand):
    help = 'Download a season of FanGraphs platoon splits and save both locally and to S3'

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

    def handle(self, *args, **options):
        season = options.get('season') or settings.CURRENT_SEASON - 1
        local_only = options.get('local_only', False)

        if not local_only and not utils.s3_manager.s3_client:
            self.stdout.write(self.style.WARNING("S3 not configured, saving locally only"))
            local_only = True

        headers = {"Content-Type": "application/json", "Referer": SPLITS_REFERER}
        for idx, (key, (position, split_id)) in enumerate(SPLITS.items(), start=1):
            self.stdout.write(f"[{idx}/{len(SPLITS)}] Downloading FanGraphs {key} splits for {season}...")
            response = utils.fg_post(
                SPLITS_URL, json=splits_payload(season, position, split_id), headers=headers, verify=False
            )
            response.raise_for_status()
            rows = rows_from_response(response.json())

            local_path = splits_local_path(season, key)
            if local_only:
                os.makedirs(os.path.dirname(local_path), exist_ok=True)
                with open(local_path, 'w') as writefile:
                    json.dump(rows, writefile, indent=2)
                self.stdout.write(f"Saved {len(rows)} {key} rows to {local_path}")
            else:
                utils.s3_manager.save_and_upload_json(rows, local_path)
                self.stdout.write(f"Saved {len(rows)} {key} rows to {local_path} and uploaded to S3")
