import csv

from dateutil.parser import *

from django.core.management.base import BaseCommand, CommandError
from ulmg import models


class Command(BaseCommand):

    def handle(self, *args, **options):
        players = models.Player.objects.filter(fangraphs_url__icontains="position=")
        for p in players:
            p.fangraphs_url = p.fangraphs_url.split('&position=')[0]
            p.save()