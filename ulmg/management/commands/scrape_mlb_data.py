import time

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from django.db.models import Count
from django.db.models import Q


import requests
from bs4 import BeautifulSoup

from ulmg import models, utils


class Command(BaseCommand):
    def handle(self, *args, **options):
        # no_birthdates = models.Player.objects.filter(birthdate__inull=True)
        players = models.Player.objects.filter(Q(position__isnull=True)|Q(birthdate__isnull=True)|Q(mlb_org__isnull=True))

        for p in players:
            if p.mlb_api_url:
                r = requests.get(p.mlb_api_url + "?hydrate=currentTeam,team")
                data = r.json()
                player = data.get('people', None)
                if player:
                    player = player[0]

                    if not p.birthdate:
                        p.birthdate = player.get('birthDate', None)

                    if not p.position:
                        p.position =  utils.normalize_pos(player['primaryPosition']['abbreviation'])

                    if not p.mlb_org:
                        mlb_org = None
                        if player.get('currentTeam'):
                            if player['currentTeam'].get('parentOrgName'):
                                org_name = player['currentTeam']['parentOrgName'].split()[-1].lower()
                                if settings.MLB_URL_TO_ORG_NAME.get(org_name):
                                    mlb_org = settings.MLB_URL_TO_ORG_NAME[org_name]
                        p.mlb_org = mlb_org

                    p.save()
                    print(p, p.birthdate, p.position, p.mlb_org)
            time.sleep(1)
