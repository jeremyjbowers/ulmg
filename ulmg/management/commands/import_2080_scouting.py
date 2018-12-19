import time

from dateutil import parser
from datetime import date
from bs4 import BeautifulSoup
from django.core.management.base import BaseCommand, CommandError
import requests
import ujson as json

from ulmg import models


class Command(BaseCommand):
    urls = [
        (2018,"2018 season","https://2080baseball.com/2018-scouting-report-library/"),
        (2018,"2018 AFL season","https://2080baseball.com/2018-arizona-league-report-library/")
    ]
    headers = {
        "accept":"*/*",
        "accept-encoding":"gzip, deflate, br",
        "accept-language":"en-US,en;q=0.9",
        "cookie":'personalization_id="v1_TFgyGIlWDoChwdtweeDfeQ=="; tfw_exp=0; syndication_guest_id=v1%3A154249083802085283; guest_id=v1%3A154249083852136227; _ga=GA1.2.1337265452.1542509130; dnt=1; ads_prefs="HBISAAA="; kdt=EAkyYvmXO4nd5CczX8kq2Kf11HPRbAvTagog6uGI; remember_checked_on=0; csrf_same_site_set=1; _twitter_sess=BAh7DCIKZmxhc2hJQzonQWN0aW9uQ29udHJvbGxlcjo6Rmxhc2g6OkZsYXNo%250ASGFzaHsABjoKQHVzZWR7ADoPY3JlYXRlZF9hdGwrCCDiCZlnAToMY3NyZl9p%250AZCIlYzIwYzg5ZGQ4MjliMGNkMzNlYzAxZDk2N2NmZDMyNWY6B2lkIiUzMTY2%250AYzg5MWI0ZmU4NzE1ODBiMzY1ZDBjMDc5Njg5ODofbG9naW5fdmVyaWZpY2F0%250AaW9uX3VzZXJfaWRpAz5XezoibG9naW5fdmVyaWZpY2F0aW9uX3JlcXVlc3Rf%250AaWQiK2ZETEwzOVZpTkZWNG05RzFaWWk5eTg4SEwwTjFjeW5YMyUyRlBLOgl1%250Ac2VyaQM%252BV3s%253D--c8edf599ba3d7af6c9032f6a8d0273e8460f2650; twid="u=8083262"; auth_token=2c813e9e0343186f18903366f183d0576798dd3b; lang=en; external_referer=padhuUp37zhkIZ%2FR84bLC1z%2F79itYVEByHqZH05SQH07SXpkOmdDiW7NDVB1R%2FE4Q3MYM24FxmU9qj92S3gcHw%3D%3D|0|GlWr2u5wzZipnVja1ZbglFG7jRzcDRbyg7bgNkbeVpYnt%2FaUtnWSmtNXJEdUZamY3K4hD6xdAsM%3D; _gid=GA1.2.1578160131.1545093151; ct0=9f865ed10d4ba1ce2847aecee213aa04; gt=1075012288745299970',
        "dnt":"1",
        "if-modified-since":"Tue, 18 Dec 2018 13:41:54 GMT",
        "origin":"https://platform.twitter.com",
        "referer":"https://platform.twitter.com/widgets/widget_iframe.e3b990b7e531827c037f99a1729ae5db.html?origin=https%3A%2F%2F2080baseball.com&settingsEndpoint=https%3A%2F%2Fsyndication.twitter.com%2Fsettings",
        "user-agent":"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_14_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/70.0.3538.110 Safari/537.36",
    }

    def handle(self, *args, **options):
        doubles = []
        for season,report,url in self.urls:
            r = requests.get(url, headers=self.headers)
            soup = BeautifulSoup(r.text, 'lxml')
            players = soup.select('#reports tbody tr')
            for p in players:
                p_cells = p.select('td')
                p_dict = {}
                p_dict['player_name'] = "%s %s" % (p_cells[0].text.strip(), p_cells[1].text.strip())
                p_dict['url'] = p_cells[0].select('a')[0].attrs['href'].strip()
                p_dict['level'] = p_cells[4].text.strip()
                p_dict['organization'] = "2080 Baseball"
                p_dict['evaluator'] = p_cells[7].text.strip()
                p_dict['date'] = "%(year)s-%(month)s-%(day)s" % dict(zip(("month", "day", "year"), (p_cells[8].text.strip().split('/'))))
                p_dict['pv'] = p_cells[9].text.strip()
                if report == "2018 season":
                    p_dict['fv'] = p_cells[10].text.strip().split()[0]
                    p_dict['risk'] = int(p_cells[10].text.strip().split()[1][0])
                    p_dict['risk_name'] = "".join(p_cells[10].text.strip().split()[1][1:])
                if report == "2018 AFL season":
                    p_dict['fv'] = "".join(p_cells[10].text[0:2])
                    p_dict['risk'] = None
                    p_dict['risk_name'] = "".join(p_cells[10].text[2:])
                p_dict['report_type'] = report
                p_dict['season'] = season

                try:
                    models.ScoutingReport.objects.get(season=season, report_type=report, url=p_dict['url'])
                except models.ScoutingReport.DoesNotExist:
                    p_detail = requests.get(p_dict['url'], headers=self.headers)
                    soup2 = BeautifulSoup(p_detail.text, 'lxml')
                    time.sleep(2)
                    birthdate = "%(year)s-%(month)s-%(day)s" % dict(zip(("month", "day", "year"), (soup2.select('div.row div.col-md-12')[1].text.strip().split(":")[1].split(" (")[0].strip().split('/'))))
                    try:
                        obj = models.Player.objects.get(first_name=p_cells[0].text.strip(), last_name=p_cells[1].text.strip(), birthdate=birthdate)
                    except models.Player.DoesNotExist:
                        raw_position = p_cells[2].text.strip()
                        if "RH" in raw_position or "LH" in raw_position:
                            position = "P"
                        if "F" in raw_position:
                            position = "OF"
                        if "B" in raw_position or raw_position == "SS":
                            position = "IF"

                        obj = models.Player(
                            first_name=p_cells[0].text.strip(),
                            last_name=p_cells[1].text.strip(),
                            level="B",
                            is_carded=False,
                            is_owned=False,
                            is_prospect=False,
                            birthdate=birthdate,
                            position=position
                        )
                        obj.save()

                    except models.Player.MultipleObjectsReturned:
                        doubles.append({"first_name":p_cells[0].text.strip(),"last_name":p_cells[1].text.strip(),"birthdate":birthdate})
                        break

                    s, created = models.ScoutingReport.objects.get_or_create(**p_dict)
                    if created:
                        s.player = obj
                        s.save()
                    print(created, s)

            with open('data/2080_doubles.json', 'w') as writefile:
                writefile.write(json.dumps(doubles))
