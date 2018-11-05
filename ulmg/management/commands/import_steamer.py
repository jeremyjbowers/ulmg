import csv
import ujson as json

from django.core.management.base import BaseCommand, CommandError
from ulmg import models


class Command(BaseCommand):
    steamer_dirty_hit_path = 'data/steamer_hitters_2019predix.csv'
    steamer_dirty_pitch_path = 'data/steamer_pitcherss_2019predix.csv'

    def handle(self, *args, **options):
        with open(self.steamer_dirty_hit_path, 'r', encoding="utf-8-sig") as readfile:
            steamerhit = csv.DictReader(readfile)
            for hit in steamerhit:
                try:
                    hit = dict(hit)
                    p = models.Player.objects.get(fangraphs_id=hit['playerid'])
                    p.steamer_predix = hit
                    print("* %s" % hit['Name'])
                except models.Player.DoesNotExist:
                    p = models.Player(
                        name=hit['Name'],
                        fangraphs_id=hit['playerid'],
                        fangraphs_url="http://www.fangraphs.com/statss.aspx?playerid=" + hit['playerid'],
                        is_owned=False,
                        is_carded=False,
                        steamer_predix=hit,
                        level="B"
                    )
                    print("+ %s" % hit['Name'])
                p.save()

        with open(self.steamer_dirty_pitch_path, 'r', encoding="utf-8-sig") as readfile:
            steamerpitch = csv.DictReader(readfile)
            for pitch in steamerpitch:
                try:
                    pitch = dict(pitch)
                    p = models.Player.objects.get(fangraphs_id=pitch['playerid'])
                    p.steamer_predix = pitch
                    print("* %s" % pitch['Name'])
                except models.Player.DoesNotExist:
                    p = models.Player(
                        name=pitch['Name'],
                        fangraphs_id=pitch['playerid'],
                        fangraphs_url="http://www.fangraphs.com/statss.aspx?playerid=" + pitch['playerid'],
                        is_owned=False,
                        is_carded=False,
                        steamer_predix=pitch,
                        level="B"
                    )
                    print("+ %s" % pitch['Name'])
                p.save()