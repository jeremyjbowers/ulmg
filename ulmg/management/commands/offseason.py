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
    def set_levels(self, *args, **options):
        print("--------- STARTERS B > A ---------")
        for p in models.Player.objects.filter(level="B", position="P", stats__career__g=21):
            p.level = "A"
            print(p)
            if not options.get("dry_run", None):
                p.save()

        print("--------- RELIEVERS B > A ---------")
        for p in models.Player.objects.filter(
            level="B", position="P", stats__career__g__gte=31, stats__career__gs=0
        ):
            p.level = "A"
            print(p)
            if not options.get("dry_run", None):
                p.save()
        print("--------- SWINGMEN B > A ---------")
        for p in models.Player.objects.filter(
            level="B", position="P", stats__career__g__gte=40, stats__career__gs__gte=15
        ):
            p.level = "A"
            print(p)
            if not options.get("dry_run", None):
                p.save()

        print("--------- HITTERS B > A ---------")
        for p in models.Player.objects.filter(level="B", stats__career__pa__gte=300):
            p.level = "A"
            print(p)
            if not options.get("dry_run", None):
                p.save()

        print("--------- STARTERS A > V ---------")
        for p in models.Player.objects.filter(level="A", position="P", stats__career__gs__gte=126):
            p.level = "V"
            print(p)
            if not options.get("dry_run", None):
                p.save()

        print("--------- RELIEVERS A > V ---------")
        for p in models.Player.objects.filter(
            level="A", position="P", stats__career__g__gte=201, stats__career__gs=0
        ):
            p.level = "V"
            print(p)
            if not options.get("dry_run", None):
                p.save()

        print("--------- SWINGMEN A > V ---------")
        for p in models.Player.objects.filter(
            level="A", position="P", stats__career__g__gte=220, stats__career__gs__gte=30
        ):
            p.level = "V"
            print(p)
            if not options.get("dry_run", None):
                p.save()

        print("--------- HITTERS A > V ---------")
        for p in models.Player.objects.filter(level="A", stats__career__pa__gte=2500):
            p.level = "V"
            print(p)
            if not options.get("dry_run", None):
                p.save()


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
        self.set_levels()
