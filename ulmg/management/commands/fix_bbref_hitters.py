from bs4 import BeautifulSoup
import requests

from django.core.management.base import BaseCommand, CommandError
from ulmg import models


class Command(BaseCommand):

    def handle(self, *args, **options):
        players = models.Player.objects\
                    .filter(
                        position="P",
                        stats__isnull=True,
                        bbref_url__isnull=False,
                        level="V",
                    )\
                    .exclude(bbref_url="")

        for p in players:
            print(p.name)
            p.carded = False
            r = requests.get(p.bbref_url)
            soup = BeautifulSoup(r.text, 'lxml')
            stats = soup.select("tr#pitching_standard.2018")
            if len(stats) > 0:
                stats = stats[0]
                stat_cols = stats.select('td')
                p.stats = {
                    "year": "2018", 
                    "gs": stat_cols[8].text.strip(),
                    "g": stat_cols[7].text.strip(),
                    "ip": stat_cols[13].text.strip(),
                    "era": stat_cols[6].text.strip(),
                    "fip": stat_cols[26].text.strip(),
                    "k9": stat_cols[31].text.strip(),
                    "bb9": stat_cols[30].text.strip()
                }

                gm = int(soup.select('table#pitching_standard tfoot tr')[0].select('td')[4].text.strip())
                st = int(soup.select('table#pitching_standard tfoot tr')[0].select('td')[5].text.strip())

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

                p.carded = True
                print(p.stats, p.level)

            p.save()