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

from ulmg import models


class Command(BaseCommand):
    def handle(self, *args, **options):
        players = models.Player.objects.filter(stats__isnull=False)
        for p in players:
            for sd in p.stats.items():
                slug = sd[0]
                stats_dict = sd[1]

                season, classification, side = slug.split('_')

                if side == "bat":
                    side = "hit"

                if side == "pit":
                    side = "pitch"

                """
                player = models.ForeignKey(Player, on_delete=models.SET_NULL, blank=True, null=True)
                season = models.IntegerField(blank=True, null=True)
                CLASSIFICATION_CHOICES = (
                    ("1-majors", "1-majors"),
                    ("2-minors", "2-minors"),
                    ("3-npb", "3-npb"),
                    ("4-kbo", "4-kbo"),
                    ("5-ncaa", "5-ncaa"),
                )
                classification = models.CharField(max_length=255, choices=CLASSIFICATION_CHOICES, null=True)
                level = models.CharField(max_length=255, blank=True, null=True)
                hit_stats = models.JSONField(null=True, blank=True)
                pitch_stats = models.JSONField(null=True, blank=True)
                """

                def standardize_classification(classification, level):
                    if classification == "majors":
                        return "1-majors"

                    if classification == "mlb":
                        return "1-majors"

                    if level == "majors":
                        return "1-majors"

                    if level == "mlb":
                        return "1-majors"

                    if classification == "minors":
                        return "2-minors"

                    for minors_level in ["DSL", "CPX", "R", "A", "A+", "AA", "AAA"]:
                        if minors_level in level:
                            return "2-minors"

                    if level == "NPB":
                        return "3-npb"

                    if level == "KBO":
                        return "4-kbo"

                    if level == "NCAA":
                        return "5-ncaa"

                    return None

                pss, created = models.PlayerStatSeason.objects.get_or_create(player=p, season=season, classification=standardize_classification(classification, stats_dict['level']), level=stats_dict['level'])

                if side == "hit":
                    pss.hit_stats = stats_dict

                if side == "pitch":
                    pss.pitch_stats = stats_dict

                pss.save()