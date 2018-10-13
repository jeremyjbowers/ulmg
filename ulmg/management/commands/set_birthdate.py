import requests
from bs4 import BeautifulSoup

from dateutil.parser import parse

from django.core.management.base import BaseCommand, CommandError
from ulmg import models

class Command(BaseCommand):

    def handle(self, *args, **options):
        for p in models.Player.objects.filter(birthdate__isnull=True, fangraphs_url__isnull=False):
            r = requests.get(p.fangraphs_url)
            soup = BeautifulSoup(r.text, 'lxml')
            bio = soup.select('div.player-info-bio')[0].text
            p.birthdate = parse(bio.split()[1])
            print(p, p.birthdate)
            p.save()