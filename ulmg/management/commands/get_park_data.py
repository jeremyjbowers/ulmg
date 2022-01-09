import csv
import ujson as json
import os
import datetime

from bs4 import BeautifulSoup
import requests
from django.apps import apps
from django.db import connection
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
import dateparser

from ulmg import models
from ulmg import utils


class Command(BaseCommand):
    def handle(self, *args, **options):

        years_range = range(2001, utils.get_current_season() + 1)

        for year in years_range:

            if not os.path.isdir(f"data/parks/{year}"):
                os.system(f"mkdir data/parks/{year}")

            url = f"https://baseballsavant.mlb.com/leaderboard/statcast-park-factors?type=year&year={year}&batSide=&stat=index_wOBA&condition=All&rolling="

            r = requests.get(url)
            soup = BeautifulSoup(r.content, "lxml")

            raw_data = (
                soup.select("div.article-template")[0]
                .select("script")[0]
                .text.split(";")[0]
                .split("var data =")[1]
                .split("var")[0]
                .strip()
            )
            parsed_data = json.loads(raw_data)

            for park in parsed_data:
                print(year, park["venue_name"])
                filename = f"data/parks/{year}/{park['venue_id']}.json"

                if not os.path.exists(filename):
                    park[
                        "venue_url"
                    ] = f"https://baseballsavant.mlb.com/leaderboard/statcast-venue?venueId={park['venue_id']}"

                    with open(filename, "w") as writefile:
                        writefile.write(json.dumps(park))
