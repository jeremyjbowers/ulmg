import json
import time

from bs4 import BeautifulSoup
from django.core.management.base import BaseCommand, CommandError
import requests

from ulmg import models


class Command(BaseCommand):

    def handle(self, *args, **options):
        for p in models.Player.objects.filter(is_35man_roster=True):
            p.is_35man_roster = False
            p.save()