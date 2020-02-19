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

from ulmg import models
from ulmg import utils


class Command(BaseCommand):

    def handle(self, *args, **options):
        def info_tranform(info):
            info = info.strip()
            if info == "med":
                return 1
            if info == "high":
                return 2
            return 0
        
        for sheet_range in settings.BOWERS_DRAFT_RANGES:
            players = utils.get_sheet(settings.BOWERS_DRAFT_SHEET, sheet_range)
            for p in players:
                obj = None
                if p.get('fg_id', None):
                    if p['fg_id'] != '':
                        try:
                            obj = models.Player.objects.get(fg_id=p['fg_id'])
                        except:
                            print(p)
                else:
                    name = "%s %s" % (p['first'], p['last'])
                    try:
                        obj = models.Player.objects.get(name=name)
                    except:
                        print(p)

                if obj:
                    obj.b_interest = int(p['interest'])
                    obj.b_info = info_tranform(p['info'])
                    obj.b_important = True
                    
                    if p.get('pl', None):
                        obj.b_pl = p['pl']

                    if p.get('fg', None):
                        obj.b_fg = p['fg']

                    if p.get('zips', None):
                        obj.b_zips = p['zips']

                    if p.get('sickels', None):
                        obj.b_sckls = p['sickels']

                    if p.get('fg_fv', None):
                        obj.b_fv = p['fg_fv']

                    if p.get('mlb', None):
                        obj.b_mlb = p['mlb']

                    if p.get('p365', None):
                        obj.b_p365 = p['p365']

                    if p.get('ba', None):
                        obj.b_ba = p['ba']

                    if p.get('bp', None):
                        obj.b_bp = p['bp']

                    obj.save()
