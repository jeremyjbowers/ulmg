import csv
import json
import os
from decimal import Decimal

from bs4 import BeautifulSoup
from dateutil.parser import parse
from django.apps import apps
from django.db import connection
from django.db.models import Avg, Sum, Count
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
import requests
import urllib3

from ulmg import models, utils


class Command(BaseCommand):

    def handle(self, *args, **options):
        no_level = models.Player.objects.filter(level=None)
        for p in no_level:
            maybe_dupe = models.Player.objects.filter(level__isnull=False, first_name=p.first_name, last_name=p.last_name, mlbam_id=None)
            if maybe_dupe:
                print(maybe_dupe)