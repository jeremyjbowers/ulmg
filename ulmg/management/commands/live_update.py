import csv
import json
import os
from decimal import Decimal

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
    def add_arguments(self, parser):
        parser.add_argument("--cached", action="store_true", help="Use cached data instead of downloading new data")

    def handle(self, *args, **options):
        requests.packages.urllib3.disable_warnings()
        urllib3.disable_warnings()

        season = utils.get_current_season()
        
        # Track successes and failures
        results = {'success': [], 'failed': []}

        if not options['cached']:
            # download roster files
            try:
                print('LIVE: Download FG rosters')
                call_command('live_download_fg_rosters')
                results['success'].append('Download FG rosters')
            except Exception as e:
                print(f'ERROR downloading FG rosters: {e}')
                results['failed'].append(f'Download FG rosters: {e}')

            try:
                print('LIVE: Fix duplicates')
                call_command('fix_dupes')
                results['success'].append('Fix duplicates')
            except Exception as e:
                print(f'ERROR fixing duplicates: {e}')
                results['failed'].append(f'Fix duplicates: {e}')

            # download mlb depth charts
            try:
                print('LIVE: Download MLB depth charts')
                call_command('live_download_mlb_depthcharts')
                results['success'].append('Download MLB depth charts')
            except Exception as e:
                print(f'ERROR downloading MLB depth charts: {e}')
                results['failed'].append(f'Download MLB depth charts: {e}')

            # fetch MLB rosters and write all_mlb_rosters.json for downstream ingest
            try:
                print('LIVE: Load MLB rosters')
                call_command('load_mlb_rosters')
                results['success'].append('Load MLB rosters')
            except Exception as e:
                print(f'ERROR loading MLB rosters: {e}')
                results['failed'].append(f'Load MLB rosters: {e}')

            # download fg stats
            try:
                print('LIVE: Download FG stats')
                call_command('live_download_fg_stats')
                results['success'].append('Download FG stats')
            except Exception as e:
                print(f'ERROR downloading FG stats: {e}')
                results['failed'].append(f'Download FG stats: {e}')

        # use roster files to update players who have fg_ids with mlb_ids
        try:
            print('LIVE: Crosswalk FGIDs to MLBIDs')
            call_command('live_crosswalk_ids')
            results['success'].append('Crosswalk FGIDs to MLBIDs')
        except Exception as e:
            print(f'ERROR crosswalking IDs: {e}')
            results['failed'].append(f'Crosswalk FGIDs to MLBIDs: {e}')
            
        try:
            call_command('fix_dupes')
            results['success'].append('Fix duplicates (post-crosswalk)')
        except Exception as e:
            print(f'ERROR fixing duplicates (post-crosswalk): {e}')
            results['failed'].append(f'Fix duplicates (post-crosswalk): {e}')

        # use roster files to update all player status
        # creates new players from FG with appropriate IDs
        try:
            print('LIVE: Update status from FG rosters')
            call_command('live_update_status_from_fg_rosters')
            results['success'].append('Update status from FG rosters')
        except Exception as e:
            print(f'ERROR updating status from FG rosters: {e}')
            results['failed'].append(f'Update status from FG rosters: {e}')

        # create new players from MLB rosters and update roster status
        try:
            print('LIVE: Update status from MLB depth charts')
            call_command('live_update_status_from_mlb_depthcharts')
            results['success'].append('Update status from MLB depth charts')
        except Exception as e:
            print(f'ERROR updating status from MLB depth charts: {e}')
            results['failed'].append(f'Update status from MLB depth charts: {e}')

        # use fg stats to update all player stats
        try:
            print('LIVE: Update stats from FG stats')
            call_command('live_update_stats_from_fg_stats')
            results['success'].append('Update stats from FG stats')
        except Exception as e:
            print(f'ERROR updating stats from FG stats: {e}')
            results['failed'].append(f'Update stats from FG stats: {e}')

        # because stats are denormalized into wishlist players, save them
        try:
            [a.save() for a in models.WishlistPlayer.objects.all()]
            results['success'].append('Update wishlist players')
        except Exception as e:
            print(f'ERROR updating wishlist players: {e}')
            results['failed'].append(f'Update wishlist players: {e}')
            
        # Print summary
        print('\n' + '='*50)
        print('LIVE UPDATE SUMMARY')
        print('='*50)
        print(f'✓ Successful ({len(results["success"])}):')
        for item in results['success']:
            print(f'  - {item}')
        
        if results['failed']:
            print(f'\n✗ Failed ({len(results["failed"])}):')
            for item in results['failed']:
                print(f'  - {item}')
        else:
            print('\n✓ All operations completed successfully!')
        print('='*50)
