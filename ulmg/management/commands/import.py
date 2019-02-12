import csv
import json
import os

from dateutil.parser import parse
from django.apps import apps
from django.db import connection
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError

from ulmg import models


class Command(BaseCommand):

    def handle(self, *args, **options):
        models.Player.objects.update(bp_prospect_rank=None, is_interesting=False, fg_prospect_fv=None, fg_prospect_rank=None, ba_prospect_rank=None, mlb_prospect_rank=None, klaw_prospect_rank=None, pl_prospect_rank=None, eta=None)

        with open('data/prospects/bowers.csv', 'r') as readfile:
            players = csv.DictReader(readfile)
            for p in players:
                obj = models.Player.objects.filter(name__search=p['name'])[0]
                obj.is_interesting = True
                obj.save()
                print(obj.name)

        with open('data/prospects/top100s.csv', 'r') as readfile:
            players = csv.DictReader(readfile)
            for p in players:
                if "Luis Garcia" in p['name']:
                    obj = models.Player.objects.get(id=3742)
                else:
                    obj = models.Player.objects.get(name=p['name'])
                obj.fg_prospect_fv = p['fv'] or None
                obj.ba_prospect_rank = p['ba'] or None
                obj.mlb_prospect_rank = p['mlb'] or None
                obj.klaw_prospect_rank = p['kl'] or None
                obj.pl_prospect_rank = p['pl'] or None
                obj.bp_prospect_rank = p['bp'] or None
                obj.js_prospect_rank = p['js'] or None
                obj.eta = p['eta'] or None
                obj.is_interesting = True
                obj.save()
                print(f"{obj.name}, {p['name']}")