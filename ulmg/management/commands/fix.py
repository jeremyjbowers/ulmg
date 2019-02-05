import json
import time

from bs4 import BeautifulSoup
from django.core.management.base import BaseCommand, CommandError
import requests

from ulmg import models


class Command(BaseCommand):

    def handle(self, *args, **options):
        def pitchers():
            for p in models.Player.objects.filter(position="P", is_carded=True,):
                if p.fg_url and 'playerid=' in p.fg_url:
                    print(p.fg_url, p.name)
                    r = requests.get(p.fg_url)
                    soup = BeautifulSoup(r.text, 'lxml')
                    if len(soup.select('tr.grid_total')) == 0:
                        p.level = "B"

                    gm = int(soup.select('tr.grid_total')[0].select('td')[5].text.strip())
                    st = int(soup.select('tr.grid_total')[0].select('td')[6].text.strip())

                    if st > 125:
                        p.level = "V"
                    elif gm > 200:
                        p.level = "V"
                    elif st < 21 and gm < 31:
                        p.level = "B"
                    elif st > 20 or gm > 31:
                        p.level = "A"
                    else:
                        p.level = None 

                    p.save()
                    time.sleep(0.5)

        pitchers()