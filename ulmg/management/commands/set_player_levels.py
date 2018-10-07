import json
import time

from bs4 import BeautifulSoup
from django.core.management.base import BaseCommand, CommandError
import requests

from ulmg import models


class Command(BaseCommand):

    def handle(self, *args, **options):
        for p in models.Player.objects.filter(level__isnull=True):
            if p.fangraphs_url and 'playerid=' in p.fangraphs_url:
                print(p.fangraphs_url, p.name)
                r = requests.get(p.fangraphs_url)
                soup = BeautifulSoup(r.text, 'lxml')
                if len(soup.select('tr.grid_total')) == 0:
                    p.level = "B"
                else:
                    if "position=P" in p.fangraphs_url:
                        gm = int(soup.select('tr.grid_total')[0].select('td')[5].text.strip())
                        st = int(soup.select('tr.grid_total')[0].select('td')[6].text.strip())

                        if st > 125:
                            p.level = "V"
                        elif gm > 200:
                            p.level = "V"
                        elif st < 21 and gm < 31:
                            p.level = "A"
                        elif st > 20 or gm > 31:
                            p.level = "B"
                        else:
                            p.level = None 

                    else:
                        pa = int(soup.select('tr.grid_total')[0].select('td')[3].text.strip())
                        if pa > 2500:
                            p.level = "V"
                        elif pa > 299:
                            p.level = "A"
                        else:
                            p.level = "B"

                p.save()
                time.sleep(0.5)