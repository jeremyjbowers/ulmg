import csv
import json
import os
import shutil
import time
import datetime

from django.core.management.base import BaseCommand, CommandError

from ulmg import models, utils

import warnings
warnings.filterwarnings("ignore")


class Command(BaseCommand):

    def handle(self, *args, **options):
        no_birthdate_players = models.Player.objects.filter(fg_id__isnull=False, birthdate__isnull=True)
        for p in no_birthdate_players:
            utils.get_fg_birthdate(p)
