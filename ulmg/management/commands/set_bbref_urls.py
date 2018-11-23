import requests
from bs4 import BeautifulSoup
import time
from django.core.management.base import BaseCommand, CommandError
from ulmg import models


class Command(BaseCommand):

    def handle(self, *args, **options):
        players = models.Player.objects.filter(bbref_url__contains="search.fcgi")

        more_than_one = []

        for p in players:
            r = requests.get("https://www.baseball-reference.com/search/search.fcgi?hint=&search=%s" % p.name.replace(' Jr.', ''), allow_redirects=False)
            if r.headers.get('Location', None):
                p.bbref_url = "https://www.baseball-reference.com" + r.headers['Location']
                p.bbref_id = p.bbref_url.split('/')[-1].split('.shtml')[0]
                print(p.bbref_url, p.bbref_id)
                p.save()
                time.sleep(0.5)
            else:
                soup = BeautifulSoup(r.text, 'lxml')
                players = soup.select('div#players div.search-item')
                if len(players) == 1:
                    player = players[0]
                    p.bbref_url = "https://www.baseball-reference.com" + player.select('div.search-item-url')[0].text.strip()
                    p.bbref_id = p.bbref_url.split('/')[-1].split('.shtml')[0]
                    print(p.bbref_url, p.bbref_id)
                    p.save()
                    time.sleep(0.5)
                else:
                    players2 = soup.select('div#players div.search-item div.search-item-name strong')
                    if len(players2) == 1:
                        player = players2[0]
                        p.bbref_url = "https://www.baseball-reference.com" + player.select('a')[0].attrs['href']
                        p.bbref_id = p.bbref_url.split('/')[-1].split('.shtml')[0]
                        print(p.bbref_url, p.bbref_id)
                        p.save()
                        time.sleep(0.5)
                    else:
                        players3 = soup.select('div#milb_players div.search-item div.search-item-name strong')
                        if len(players3) == 1:
                            player = players3[0]
                            p.bbref_url = "https://www.baseball-reference.com" + player.select('a')[0].attrs['href']
                            p.bbref_id = p.bbref_url.split('/')[-1].split('.shtml')[0]
                            print(p.bbref_url, p.bbref_id)
                            p.save()
                            time.sleep(0.5)
                        else:
                            more_than_one.append("%s|%s" % (p.name, p.id))
                            print(p.name, " more than one")

        with open('data/more_than_one.txt', 'w') as writefile:
            writefile.write("\n".join(more_than_one))
