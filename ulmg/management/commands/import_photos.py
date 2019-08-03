import csv
import ujson as json
import os

from bs4 import BeautifulSoup
import requests

from dateutil.parser import parse
from django.apps import apps
from django.db import connection
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError

from ulmg import models


class Command(BaseCommand):

    def handle(self, *args, **options):
        players = models.Player.objects.filter(bref_url__isnull=False, bref_img__isnull=True)
        for p in players:
            if p.bref_url != "":
                r = requests.get(p.bref_url)
                soup = BeautifulSoup(r.content, 'lxml')
                img = soup.select('div#meta div.media-item img')
                try:
                    image = img[0].attrs['src']
                    p.bref_img = image
                    p.save()
                    print(p.name, image)
                except:
                    pass