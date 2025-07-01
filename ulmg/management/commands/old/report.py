import csv
import requests
from bs4 import BeautifulSoup

from django.core.management.base import BaseCommand, CommandError

from ulmg import models


class Command(BaseCommand):
    def handle(self, *args, **kwargs):
        r = requests.get('https://www.baseballamerica.com/stories/top-500-fantasy-baseball-dynasty-rankings-for-2025/')
        soup = BeautifulSoup(r.content)
        players = soup.select('.wp-block-table table tbody tr')
        print(players)


    # def handle(self, *args, **options):
    #     players = []
    #     for team in models.Team.objects.all():
    #         players += [
    #             p
    #             for p in models.Player.objects.filter(team=team).values(
    #                 "name", "team__abbreviation", "level"
    #             )
    #         ]

    #     with open("for_rus.csv", "w") as writefile:
    #         fieldnames = players[0].keys()
    #         writer = csv.DictWriter(writefile, fieldnames)

    #         writer.writeheader()
    #         for player in players:
    #             writer.writerow(player)
