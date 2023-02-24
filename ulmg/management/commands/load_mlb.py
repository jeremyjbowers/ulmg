import csv
import json
import os
import time

from bs4 import BeautifulSoup
import requests
from django.apps import apps
from django.db import connection
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
import dateparser
import random

from ulmg import models
from ulmg import utils

"""
{
    "people":[
        {
            "id":661536,
            "fullName":"Melvin Adon",
            "firstName":"Melvin",
            "lastName":"Adon",
            "birthDate":"1994-06-09",
            "currentTeam":{
                "name":"San Francisco Giants"
            },
            "primaryPosition":{"code":"1","name":"Pitcher","type":"Pitcher","abbreviation":"P"},"useName":"Melvin",
    ]
}
"""

class Command(BaseCommand):
    def handle(self, *args, **options):

        players = models.Player.objects.filter(mlbam_id__isnull=True, mlbam_checked=False)

        for obj in players:

            search_url = f"https://statsapi.mlb.com/api/v1/people/search?names={obj.name}&sportIds=11,12,13,14,15,5442,16&active=true&hydrate=currentTeam,team"
            print(search_url)

            try:
                r = requests.get(search_url, timeout=5)

                results = r.json().get('people', None)

                if len(results) == 1:
                    p = results[0]
                    obj.mlbam_id = p['id']
                    obj.birthdate = p['birthDate']
                    obj.mlb_team = p['currentTeam']['name']
                    obj.mlb_team_abbr = p['currentTeam']['abbreviation']
                    print(f"++ {obj}")
                else:
                    print(f"   {obj}")
                
                obj.mlbam_checked = True
                obj.save()

                time.sleep(random.randrange(1,4))

            except requests.exceptions.ReadTimeout:
                pass

            except requests.exceptions.ConnectionError:
                pass

        with open('data/mlb_2_fg_cross.json', 'w') as writefile:
            writefile.write(json.dumps([{"fg_id": p.fg_id, "mlbam_id": p.mlbam_id} for p in models.Player.objects.filter(mlbam_id__isnull=False, fg_id__isnull=False)]))