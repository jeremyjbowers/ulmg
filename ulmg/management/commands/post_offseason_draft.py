import csv
import ujson as json
import os

from dateutil.parser import parse
from django.apps import apps
from django.db import connection
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Count, Avg, Sum, Max, Min, Q
from django.conf import settings

from ulmg import models


class Command(BaseCommand):
    def set_carded(self, *args, **optionals):
        print(".... setting carded status")

    def reset_rosters(self):
        print(".... resetting rosters")
        models.Player.objects.filter(is_mlb_roster=True).update(is_mlb_roster=False)
        models.Player.objects.filter(is_aaa_roster=True).update(is_aaa_roster=False)
        models.Player.objects.filter(is_1h_c=True).update(is_1h_c=False)
        models.Player.objects.filter(is_1h_p=True).update(is_1h_p=False)
        models.Player.objects.filter(is_1h_pos=True).update(is_1h_pos=False)
        models.Player.objects.filter(is_2h_c=True).update(is_2h_c=False)
        models.Player.objects.filter(is_2h_p=True).update(is_2h_p=False)
        models.Player.objects.filter(is_2h_pos=True).update(is_2h_pos=False)
        models.Player.objects.filter(is_reserve=True).update(is_reserve=False)

    def handle(self, *args, **options):
        self.reset_rosters()
        # self.set_carded()
