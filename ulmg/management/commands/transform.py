import csv
import json
import os

from bs4 import BeautifulSoup
from django.apps import apps
from django.db import connection
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError

from ulmg import models


class Command(BaseCommand):

    def handle(self, *args, **options):

        def normalize_pos(pos):
            if pos.upper() in ["1B", "2B", "3B", "SS"]:
                pos = "IF"
            if pos.upper() in ["RF", "CF", "LF"]:
                pos = "OF"
            if "P" in pos.upper():
                pos = "P"
            return pos

        pass
            