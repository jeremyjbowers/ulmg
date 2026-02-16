# ABOUTME: ARCHIVED - Original scrape_mlb_data. See documents/MLB_DATA_PIPELINE_RECOMMENDATION.md
# ABOUTME: Uses player.mlb_api_url to fetch birthdate, position, mlb_org from MLB API.
import time
from django.core.management.base import BaseCommand
from django.db.models import Q
import requests
from ulmg import models, utils


class Command(BaseCommand):
    def handle(self, *args, **options):
        players = models.Player.objects.exclude(mlbam_id__isnull=True).filter(
            Q(position__isnull=True) | Q(birthdate__isnull=True)
        )
        for p in players:
            if p.mlb_api_url:
                r = requests.get(p.mlb_api_url + "?hydrate=currentTeam,team")
                data = r.json()
                player = data.get('people')
                if player:
                    player = player[0]
                    if not p.birthdate:
                        p.birthdate = player.get('birthDate')
                    if not p.position:
                        p.position = utils.normalize_pos(player['primaryPosition']['abbreviation'])
                    if not p.mlb_org and player.get('currentTeam'):
                        mlb_org = None
                        if player['currentTeam'].get('parentOrgName'):
                            org_name = player['currentTeam']['parentOrgName'].split()[-1].lower()
                            if hasattr(settings, 'MLB_URL_TO_ORG_NAME') and settings.MLB_URL_TO_ORG_NAME.get(org_name):
                                mlb_org = settings.MLB_URL_TO_ORG_NAME[org_name]
                        p.mlb_org = mlb_org
                    p.save()
                time.sleep(1)
