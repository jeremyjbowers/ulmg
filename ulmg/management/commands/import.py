import csv
import ujson as json
import os

from dateutil.parser import parse
from django.apps import apps
from django.db import connection
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError

from ulmg import models


class Command(BaseCommand):
    """
    key_person,key_uuid,key_mlbam,key_retro,key_bbref,key_bbref_minors,key_fangraphs,key_npb,key_sr_nfl,key_sr_nba,key_sr_nhl,key_findagrave,name_last,name_first,name_given,name_suffix,name_matrilineal,name_nick,birth_year,birth_month,birth_day,death_year,death_month,death_day,pro_played_first,pro_played_last,mlb_played_first,mlb_played_last,col_played_first,col_played_last,pro_managed_first,pro_managed_last,mlb_managed_first,mlb_managed_last,col_managed_first,col_managed_last,pro_umpired_first,pro_umpired_last,mlb_umpired_first,mlb_umpired_last
    from: https://github.com/chadwickbureau/register/tree/master/data
    """

    def gen_people_map(self):
        people_map = {}

        os.system('cd ../register && git pull origin master')

        with open('../register/data/people.csv', 'r') as readfile:
            for c in csv.DictReader(readfile):
                if c['key_fangraphs'] != "":
                    people_map[c['key_fangraphs']] = dict(c)
        
        with open('data/ulmg/people_map.json', 'w') as writefile:
            writefile.write(json.dumps(people_map))

    def load_mlbam_ids(self):
        models.Player.objects.update(mlbam_id=None)
        with open('data/ulmg/people_map.json', 'r') as readfile:
            people_map = json.loads(readfile.read())

            for p in models.Player.objects.filter(fg_id__isnull=False):
                z = people_map.get(p.fg_id, None)
                if z:
                    if z['key_mlbam'] != "":
                        p.mlbam_id = z['key_mlbam']
                        p.save()
                        print(p)

    def handle(self, *args, **options):
        # self.gen_people_map()
        self.load_mlbam_ids()