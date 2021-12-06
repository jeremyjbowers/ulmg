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

from ulmg import models, utils


class Command(BaseCommand):

    def handle(self, *args, **options):
        utils.reset_rosters()

        # Unprotect all V and A players prior to the 35-man roster.
        models.Player.objects.filter(is_owned=True, level__in=["A", "V"]).update(
            is_protected=False
        )
        models.Player.objects.filter(
            is_owned=True, is_carded=False, level__in=["A", "V"]
        ).update(is_protected=True)

        utils.set_carded()
        utils.load_career_hit()
        utils.load_career_pitch()
        utils.set_levels()
