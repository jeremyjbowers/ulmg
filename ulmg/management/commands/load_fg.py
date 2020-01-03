import csv
import json
import os
from decimal import Decimal

from dateutil.parser import parse
from django.apps import apps
from django.db import connection
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from nameparser import HumanName

from ulmg import models


class Command(BaseCommand):

    def handle(self, *args, **options):
        pass