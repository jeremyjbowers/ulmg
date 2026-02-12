import csv
import json
import os
from decimal import Decimal

import urllib3

from bs4 import BeautifulSoup
from dateutil.parser import parse
from django.apps import apps
from django.db import connection
from django.db.models import Avg, Sum, Count
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
import requests

from ulmg import models, utils

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class Command(BaseCommand):
    help = 'Download current season FanGraphs stats data and save both locally and to S3'

    def add_arguments(self, parser):
        parser.add_argument(
            '--local-only',
            action='store_true',
            help='Save files locally only, skip S3 upload'
        )

    def get_fg_major_hitter_season(self):
        url = f"https://www.fangraphs.com/api/leaders/major-league/data?age=0&pos=all&stats=bat&lg=all&qual=0&season={self.season}&season1={self.season}&startdate={self.season}-01-01&enddate={self.season}-12-31&month=0&team=0&pageitems=5000&pagenum=1&ind=0&rost=0&players=0&type=c%2C6%2C-1%2C312%2C305%2C309%2C306%2C307%2C308%2C310%2C311%2C-1%2C23%2C315%2C-1%2C38%2C316%2C-1%2C50%2C317%2C7%2C8%2C9%2C10%2C11%2C12%2C13%2C14%2C21%2C23%2C34%2C35%2C37%2C38%2C39%2C40%2C41%2C50%2C52%2C57%2C58%2C61%2C62%2C5&sortdir=desc&sortstat=Events"
        rows = requests.get(url, verify=False).json()['data']

        local_path = f'data/{self.season}/fg_mlb_bat.json'
        if self.local_only:
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            with open(local_path, 'w') as writefile:
                json.dump(rows, writefile, indent=2)
            self.stdout.write(f"Saved MLB batting data to {local_path}")
        else:
            utils.s3_manager.save_and_upload_json(rows, local_path)
            self.stdout.write(f"Saved MLB batting data to {local_path} and uploaded to S3")

    def get_fg_major_pitcher_season(self):
        url = f"https://www.fangraphs.com/api/leaders/major-league/data?age=0&pos=all&stats=pit&lg=all&qual=2&season={self.season}&season1={self.season}&startdate={self.season}-01-01&enddate={self.season}-12-31&month=0&team=0&pageitems=5000&pagenum=1&ind=0&rost=0&players=0&type=c%2C4%2C5%2C11%2C7%2C8%2C13%2C-1%2C24%2C19%2C15%2C18%2C36%2C37%2C40%2C43%2C44%2C48%2C51%2C-1%2C240%2C-1%2C6%2C332%2C45%2C62%2C122%2C-1%2C59%2C17%2C301%2C302%2C303%2C117%2C118%2C119&sortdir=desc&sortstat=SO"
        rows = requests.get(url, verify=False).json()['data']

        local_path = f'data/{self.season}/fg_mlb_pit.json'
        if self.local_only:
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            with open(local_path, 'w') as writefile:
                json.dump(rows, writefile, indent=2)
            self.stdout.write(f"Saved MLB pitching data to {local_path}")
        else:
            utils.s3_manager.save_and_upload_json(rows, local_path)
            self.stdout.write(f"Saved MLB pitching data to {local_path} and uploaded to S3")

    def get_fg_minor_season(self):
        headers = {"accept": "application/json"}
        players = {"bat": [], "pit": []}

        for k, v in players.items():
            url = f"https://www.fangraphs.com/api/leaders/minor-league/data?pos=all&level=0&lg=2,4,5,6,7,8,9,10,11,14,12,13,15,16,17,18,30,32&stats={k}&qual=0&type=0&team=&season={self.season}&seasonEnd={self.season}&org=&ind=0&splitTeam=false"
            r = requests.get(url, verify=False)
            players[k] += r.json()

        for k, v in players.items():
            local_path = f'data/{self.season}/fg_milb_{k}.json'
            if self.local_only:
                # Create directory if it doesn't exist
                os.makedirs(os.path.dirname(local_path), exist_ok=True)
                with open(local_path, 'w') as writefile:
                    json.dump(v, writefile, indent=2)
                self.stdout.write(f"Saved MiLB {k} data to {local_path}")
            else:
                utils.s3_manager.save_and_upload_json(v, local_path)
                self.stdout.write(f"Saved MiLB {k} data to {local_path} and uploaded to S3")

    def get_fg_college_season(self):
        headers = {"accept": "application/json"}
        players = {"bat": [], "pit": []}

        for k, v in players.items():
            url = f"https://www.fangraphs.com/api/leaders/college/data?position=&type=0&stats={k}&qual=y&seasonstart={self.season}&seasonend={self.season}&team=0&players=0&conference=0&pageitems=2000000000"
            r = requests.get(url, verify=False)
            players[k] += r.json().get('data')

        for k, v in players.items():
            local_path = f'data/{self.season}/fg_college_{k}.json'
            if self.local_only:
                # Create directory if it doesn't exist
                os.makedirs(os.path.dirname(local_path), exist_ok=True)
                with open(local_path, 'w') as writefile:
                    json.dump(v, writefile, indent=2)
                self.stdout.write(f"Saved college {k} data to {local_path}")
            else:
                utils.s3_manager.save_and_upload_json(v, local_path)
                self.stdout.write(f"Saved college {k} data to {local_path} and uploaded to S3")

    def get_fg_npb_season(self):
        headers = {"accept": "application/json"}
        players = {"bat": [], "pit": []}

        for k, v in players.items():
            url = f"https://www.fangraphs.com/api/leaders/international/npb/data?lg=&pos=all&qual=0&stats={k}&type=1&seasonstart={self.season}&seasonend={self.season}&team=0&season={self.season}&org=&ind=0&pageitems=2000000000"
            r = requests.get(url, verify=False)
            players[k] += r.json()

        for k, v in players.items():
            local_path = f'data/{self.season}/fg_npb_{k}.json'
            if self.local_only:
                # Create directory if it doesn't exist
                os.makedirs(os.path.dirname(local_path), exist_ok=True)
                with open(local_path, 'w') as writefile:
                    json.dump(v, writefile, indent=2)
                self.stdout.write(f"Saved NPB {k} data to {local_path}")
            else:
                utils.s3_manager.save_and_upload_json(v, local_path)
                self.stdout.write(f"Saved NPB {k} data to {local_path} and uploaded to S3")

    def get_fg_kbo_season(self):
        headers = {"accept": "application/json"}
        players = {"bat": [], "pit": []}

        for k, v in players.items():
            url = f"https://www.fangraphs.com/api/leaders/international/kbo/data?lg=&pos=all&qual=0&stats={k}&type=1&seasonstart={self.season}&seasonend={self.season}&team=0&season={self.season}&org=&ind=0&pageitems=2000000000"
            r = requests.get(url, verify=False)
            players[k] += r.json()

        for k, v in players.items():
            local_path = f'data/{self.season}/fg_kbo_{k}.json'
            if self.local_only:
                # Create directory if it doesn't exist
                os.makedirs(os.path.dirname(local_path), exist_ok=True)
                with open(local_path, 'w') as writefile:
                    json.dump(v, writefile, indent=2)
                self.stdout.write(f"Saved KBO {k} data to {local_path}")
            else:
                utils.s3_manager.save_and_upload_json(v, local_path)
                self.stdout.write(f"Saved KBO {k} data to {local_path} and uploaded to S3")

    def handle(self, *args, **options):
        self.season = utils.get_current_season()
        self.local_only = options.get('local_only', False)

        if self.local_only:
            self.stdout.write("Running in local-only mode, will not upload to S3")
        elif not utils.s3_manager.s3_client:
            self.stdout.write(self.style.WARNING("S3 not configured, saving locally only"))
            self.local_only = True
        
        self.stdout.write(f"Downloading FanGraphs data for {self.season} season...")
        
        # Track successes and failures
        results = {'success': [], 'failed': []}
        
        operations = [
            ('MLB Hitters', self.get_fg_major_hitter_season),
            ('MLB Pitchers', self.get_fg_major_pitcher_season),
            ('Minor League Players', self.get_fg_minor_season),
            ('College Players', self.get_fg_college_season),
            ('NPB Players', self.get_fg_npb_season),
            ('KBO Players', self.get_fg_kbo_season),
        ]
        
        for operation_name, operation_func in operations:
            try:
                self.stdout.write(f'Downloading {operation_name}...')
                operation_func()
                results['success'].append(operation_name)
                self.stdout.write(f'✓ {operation_name} downloaded successfully')
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'✗ ERROR downloading {operation_name}: {e}'))
                results['failed'].append(f'{operation_name}: {str(e)}')
                # Continue with next operation
                continue
        
        # Print summary
        self.stdout.write('\n' + '='*50)
        self.stdout.write('FG DOWNLOAD SUMMARY')
        self.stdout.write('='*50)
        self.stdout.write(f'✓ Successful ({len(results["success"])}):')
        for item in results['success']:
            self.stdout.write(f'  - {item}')
        
        if results['failed']:
            self.stdout.write(f'\n✗ Failed ({len(results["failed"])}):')
            for item in results['failed']:
                self.stdout.write(f'  - {item}')
        else:
            self.stdout.write('\n✓ All operations completed successfully!')
        self.stdout.write('='*50)
        
        if results['success']:
            self.stdout.write(self.style.SUCCESS(f"Downloaded {len(results['success'])} out of {len(operations)} FanGraphs data sources for {self.season}"))
