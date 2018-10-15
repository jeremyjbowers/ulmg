import requests
import time
from django.core.management.base import BaseCommand, CommandError
from ulmg import models


class Command(BaseCommand):

    def handle(self, *args, **options):
        players = models.Player.objects.filter(bbref_url__isnull=True)
        
        for p in players:
            r = requests.get("https://www.baseball-reference.com/search/search.fcgi?hint=&search=%s" % p.name, allow_redirects=False)
            if r.headers.get('Location', None):
                p.bbref_url = "https://www.baseball-reference.com" + r.headers['Location']
                p.bbref_id = p.bbref_url.split('/')[-1].split('.shtml')[0]
                print(p.bbref_url, p.bbref_id)
                p.save()
                time.sleep(0.5)