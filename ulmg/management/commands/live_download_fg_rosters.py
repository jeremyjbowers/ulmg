import csv
import json
import os
import time

from bs4 import BeautifulSoup
from dateutil.parser import parse
from django.apps import apps
from django.db import connection
from django.db.models import Avg, Sum, Count
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
import requests
import urllib3

from ulmg import models, utils


class Command(BaseCommand):
    help = 'Download FanGraphs roster data and save both locally and to S3'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--local-only',
            action='store_true',
            help='Save files locally only, skip S3 upload'
        )

    def handle(self, *args, **options):
        urllib3.disable_warnings()
        
        local_only = options.get('local_only', False)
        
        if local_only:
            self.stdout.write("Running in local-only mode, will not upload to S3")
        elif not utils.s3_manager.s3_client:
            self.stdout.write(self.style.WARNING("S3 not configured, saving locally only"))
            local_only = True

        teams = settings.ROSTER_TEAM_IDS

        self.stdout.write(f"Downloading roster data for {len(teams)} teams...")

        # Track successes and failures
        results = {'success': [], 'failed': []}

        for team_id, team_abbrev, team_name in teams:
            try:
                url = f"https://www.fangraphs.com/api/depth-charts/roster?teamid={team_id}"

                r = requests.get(url, verify=False)
                print(r.status_code, url)
                if r.status_code == 200:
                    roster = r.json()
                    local_path = f"data/rosters/{team_abbrev}_roster.json"
                    
                    if local_only:
                        # Create directory if it doesn't exist
                        os.makedirs(os.path.dirname(local_path), exist_ok=True)
                        with open(local_path, "w") as writefile:
                            json.dump(roster, writefile, indent=2)
                        self.stdout.write(f"Saved {team_name} roster to {local_path}")
                    else:
                        utils.s3_manager.save_and_upload_json(roster, local_path)
                        self.stdout.write(f"Saved {team_name} roster to {local_path} and uploaded to S3")
                    
                    results['success'].append(team_name)
                else:
                    self.stderr.write(f"Failed to download {team_name} roster: HTTP {r.status_code}")
                    results['failed'].append(f"{team_name}: HTTP {r.status_code}")

                time.sleep(5)
                
            except Exception as e:
                self.stderr.write(f"ERROR downloading {team_name} roster: {e}")
                results['failed'].append(f"{team_name}: {str(e)}")
                continue

        # Print summary
        self.stdout.write('\n' + '='*40)
        self.stdout.write('FG ROSTER DOWNLOAD SUMMARY')
        self.stdout.write('='*40)
        self.stdout.write(f'✓ Successful ({len(results["success"])}):')
        for team in results['success']:
            self.stdout.write(f'  - {team}')
        
        if results['failed']:
            self.stdout.write(f'\n✗ Failed ({len(results["failed"])}):')
            for team in results['failed']:
                self.stdout.write(f'  - {team}')
        else:
            self.stdout.write('\n✓ All teams downloaded successfully!')
        self.stdout.write('='*40)
        
        if results['success']:
            self.stdout.write(self.style.SUCCESS(f"Downloaded {len(results['success'])} out of {len(teams)} team rosters"))