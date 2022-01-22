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

from ulmg import models
import statsapi

import datetime
import pytz


class Command(BaseCommand):
    def handle(self, *args, **options):
        call_command('migrate')
        call_command('collectstatic')
        # call_command('load_strat_ratings')