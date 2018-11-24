import requests
from bs4 import BeautifulSoup
import time
from django.core.management.base import BaseCommand, CommandError
from ulmg import models


class Command(BaseCommand):
    def to_even(self, num):
        if num % 2 == 0:
            return num
        else:
            return num - 1

    def handle(self, *args, **options):
        URL = "https://ulmg.wordpress.com/trades/"
        r = requests.get(URL)

        if int(r.status_code) == 200:
            trades = []

            soup = BeautifulSoup(r.text, 'lxml')

            seasons = []
            for t in [s for s in soup.select('div.entry h3') if "20" in s.text]:
                if t.text.strip() == "Winter Hot Stove 2011-12":
                    seasons.append('2012')
                    seasons.append('2012')
                if "trades" in t.text:
                    seasons.append(t.text.split(' trades')[0].strip())
                    seasons.append(t.text.split(' trades')[0].strip())
                if "Stove" in t.text:
                    seasons.append(t.text.split('Stove')[1].strip())
                    seasons.append(t.text.split('Stove')[1].strip())

            for idx,b in enumerate(soup.select('div.entry ul')[:-1]):
                season = seasons[idx]
                for trade in b.select('li'):
                    trade_dict = {"season": season}
                    trade_dict['summary'] = trade.text.strip().replace(u'\xa0', ' ')
                    trade_dict['trade_type'] = "players only"
                    if "#" in trade_dict['summary']:
                        trade_dict['trade_type'] = "players and picks"
                    obj, created = models.TradeSummary.objects.get_or_create(**trade_dict)
                    if created:
                        print('+ %s' % obj)
                    else:
                        print('* %s' % obj)