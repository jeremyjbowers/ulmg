import requests
from bs4 import BeautifulSoup
import time
from django.core.management.base import BaseCommand, CommandError
from ulmg import models


class Command(BaseCommand):

    def handle(self, *args, **options):
        # with open('data/more_than_one.txt', 'r') as readfile:
        #     players_ids = [p.split('|') for p in readfile.read().split('\n')]

        # players = models.Player.objects.filter(id__in=[id for _,id in players_ids])

        players = ["http://theulmg.com/admin/ulmg/player/%s/change/" % p.id for p in models.Player.objects.filter(bbref_url__isnull=True)]

        with open('data/blank_bbref.txt', 'w') as writefile:
            writefile.write("\n".join(players))