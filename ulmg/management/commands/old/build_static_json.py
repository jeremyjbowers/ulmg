import os
import glob

import ujson as json
import boto3
from botocore.config import Config
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings

from ulmg import models, utils


class Command(BaseCommand):
    teams = None
    players = None
    drafts = None
    trades = None

    local_build_route = 'public/'

    def __init__(self, *args, **options):
        self.teams = models.Team.objects.all()


    def deliver_public(self):
        files = glob.glob(f'{self.local_build_route}*/*')

        session = boto3.session.Session()
        client = session.client('s3',
                        region_name=settings.AWS_S3_REGION_NAME,
                        endpoint_url=settings.AWS_S3_ENDPOINT_URL,
                        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY)

        for local_path in files:
            key_name = local_path.replace('public', 'api/v1')
            print(f"https://{settings.AWS_S3_CUSTOM_DOMAIN}/{key_name}")
            client.upload_file(local_path, settings.AWS_STORAGE_BUCKET_NAME, key_name, ExtraArgs={'ACL':'public-read'})
        

    def all_teams(self):
        print("All teams")
        payload = [team.to_api_obj() for team in models.Team.objects.all()]
        with open(f'{self.local_build_route}all/teams.json', 'w') as writefile:
                writefile.write(json.dumps(payload))


    def all_players(self):
        print("All players")
        payload = [player.to_api_obj() for player in models.Player.objects.all()]
        with open(f'{self.local_build_route}all/players.json', 'w') as writefile:
                writefile.write(json.dumps(payload))


    def all_picks(self):
        print("All picks")
        payload = [pick.to_api_obj() for pick in models.DraftPick.objects.all().order_by("-year", "season", "draft_type", "draft_round", "pick_number")]
        with open(f'{self.local_build_route}all/picks.json', 'w') as writefile:
                writefile.write(json.dumps(payload))


    def all_trades(self):
        print("All trades")
        payload = [trade.summary_dict() for trade in models.Trade.objects.all().order_by("-date")]
        with open(f'{self.local_build_route}all/trades.json', 'w') as writefile:
                writefile.write(json.dumps(payload))


    def team_trades_json(self):
        print("Trades by team")
        for team in self.teams:
            print(f"{team.abbreviation}")
            payload = {}
            team_receipts = models.TradeReceipt.objects.filter(team=team, trade__isnull=False).order_by("-trade__date")
            payload['trades'] = [tr.trade.summary_dict() for tr in team_receipts]
            payload['team'] = team.to_api_obj()

            with open(f'{self.local_build_route}{team.abbreviation.lower()}/trades.json', 'w') as writefile:
                writefile.write(json.dumps(payload))


    def team_picks_json(self):
        print("Picks by team")
        for team in self.teams:
            print(f"{team.abbreviation}")
            payload = {}
            team_picks = models.DraftPick.objects.filter(team=team).order_by("-year", "season", "draft_type", "draft_round", "pick_number")
            
            payload['team'] = team.to_api_obj()
            payload['picks'] = [pick.to_api_obj() for pick in team_picks]

            with open(f'{self.local_build_route}{team.abbreviation.lower()}/picks.json', 'w') as writefile:
                writefile.write(json.dumps(payload))


    def team_roster_json(self):
        print("Rosters by team")
        for team in self.teams:
            print(f"{team.abbreviation}")
            payload = {}
            team_players = models.Player.objects.filter(team=team)

            payload['team'] = team.to_api_obj()
            payload['players'] = [player.to_api_obj() for player in team_players]

            with open(f'{self.local_build_route}{team.abbreviation.lower()}/roster.json', 'w') as writefile:
                writefile.write(json.dumps(payload))
            

    def handle(self, *args, **options):
        if not os.path.isdir(f'{self.local_build_route}'):
            os.mkdir(f'{self.local_build_route}')

        for team in self.teams:
            if not os.path.isdir(f'{self.local_build_route}{team.abbreviation.lower()}'):
                os.mkdir(f'{self.local_build_route}{team.abbreviation.lower()}')

        if not os.path.isdir(f'{self.local_build_route}all'):
                os.mkdir(f'{self.local_build_route}all')

        self.team_roster_json()
        self.team_picks_json()
        self.team_trades_json()
        self.all_trades()
        self.all_picks()
        self.all_players()

        self.deliver_public()
        