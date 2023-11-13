import csv
import json
import os
from decimal import Decimal

from bs4 import BeautifulSoup
from dateutil.parser import parse
from django.apps import apps
from django.db import connection
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
import requests

from ulmg import models, utils

import datetime
import pytz


class Command(BaseCommand):
    def handle(self, *args, **options):
        call_command("migrate")
        call_command("collectstatic", "--noinput")


        call_command('generate_draft_order', '2024', 'offseason', "aa", "data/ulmg/2024-offseason-aa-order.txt")
        call_command('generate_draft_order', '2024', 'offseason', "open", "data/ulmg/2024-offseason-open-order.txt")
        call_command('offseason')
        # call_command('import_defense', '2022')
        # call_command('scrape_birthdates')
        # call_command('post_offseason_draft')
        # call_command('generate_draft_picks','2024','offseason')
        # call_command('generate_draft_picks','2024','midseason')
        # call_command('midseason')
        # call_command('live_update')