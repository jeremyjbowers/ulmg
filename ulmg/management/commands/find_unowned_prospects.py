import json
import time

from bs4 import BeautifulSoup
from django.core.management.base import BaseCommand, CommandError
import requests

from ulmg import models
from ulmg import utils


class Command(BaseCommand):
    def handle(self, *args, **options):
        with open("prospects/ftx.json", "r") as readfile:
            ftx = json.loads(readfile.read())
            for p in ftx:
                hit = utils.fuzzy_find_player(p["name"])
                if len(hit) == 0:
                    print(f"n {p}")

                if len(hit) == 1:
                    hit = hit[0]
                    if not hit.is_owned:
                        print(f"u {p}")
