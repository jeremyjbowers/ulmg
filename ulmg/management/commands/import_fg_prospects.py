import csv
from io import StringIO
import json
import os

from django.core.management import call_command
from django.db import connection
from django.core.management.base import BaseCommand, CommandError

from ulmg import models


class Command(BaseCommand):
    int_url="https://www.fangraphs.com/api/prospects/board/prospects-list?draft=%(year)sint&valueHeader=int"
    draft_url="https://www.fangraphs.com/api/prospects/board/prospects-list?draft=%(year)smlb&valueHeader=mlb"
    prospect_update_url="https://www.fangraphs.com/api/prospects/board/prospects-list?draft=%(year)supdated&valueHeader=prospect"
    prospect_url="https://www.fangraphs.com/api/prospects/board/prospects-list?draft=%(year)sprospect&valueHeader=prospect"

    def make_none(self, rank):
        if rank == "":
            return None
        return int(rank)

    def reset_scouting_reports(self):
        models.ScoutingReport.objects.all().delete()

    def get_data(self, url, file_path):
            os.system('curl -o "%s" "%s"' % (file_path, url))

    def download_data(self, draft_years, prospect_years, int_years):
        for year in prospect_years:
            url = self.prospect_update_url % {"year": year}
            file_path = 'data/fgapi-%s-prospect-update.json' % year
            if not os.path.isfile(file_path):
                self.get_data(url, file_path)

        for year in prospect_years:
            url = self.prospect_url % {"year": year}
            file_path = 'data/fgapi-%s-prospect.json' % year
            if not os.path.isfile(file_path):
                self.get_data(url, file_path)

        for year in int_years:
            url = self.int_url % {"year": year}
            file_path = 'data/fgapi-%s-int.json' % year
            if not os.path.isfile(file_path):
                self.get_data(url, file_path)
  
        for year in draft_years:
            url = self.draft_url % {"year": year}
            file_path = 'data/fgapi-%s-draft.json' % year
            if not os.path.isfile(file_path):
                self.get_data(url, file_path)

    def handle(self, *args, **options):
        draft_years = ['2018', '2019', '2020', '2021']
        prospect_years = ['2018']
        int_years = ['2016', '2017', '2018']

        self.reset_scouting_reports()
        # self.download_data(draft_years, prospect_years, int_years)

        for year in prospect_years:
            file_path = 'data/fgapi-%s-prospect-update.json' % year
            with open(file_path, 'r') as readfile:
                players = json.loads(readfile.read())
                for p in players:
                    if p['PlayerId'] != '':
                        try:
                            obj = models.Player.objects.get(fg_id=p['PlayerId'])
                        except models.Player.DoesNotExist:
                            try:
                                obj = models.Player.objects.get(name=p['playerName'])
                            except models.Player.DoesNotExist:
                                print("Has id: %s" % p['playerName'])
                    else:
                        try:
                            obj = models.Player.objects.get(name=p['playerName'])
                        except models.Player.DoesNotExist:
                            print("No id: %s" % p['playerName'])

        # for p in players:
        #     obj, created = models.Player.objects.get_or_create(name=p['Name'])
        #     if created:
        #         print("+ %s" % obj)
        #     else:
        #         print("* %s" % obj)

        #     obj2, created = models.ScoutingReport.objects.get_or_create(
        #         player=obj,
        #         year=2018,
        #         month=6,
        #         publication="fg",
        #         fv=p['FV'],
        #         rank=make_none(p['Rk']),
        #         rank_type="2018 Fangraphs Top J2",
        #         notes=p['Report']
        #     )