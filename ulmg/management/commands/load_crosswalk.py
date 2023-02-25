import csv
import glob

import ujson as json

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings

from ulmg import models


"""
key_uuid: The primary key, providing the most stable reference to a person. Guaranteed not to be re-issued to a different person in the future.
key_person: The first eight (hex) digits of the key_uuid. It is guaranteed that this is unique at any given time. However, should a person's record be withdrawn from the register, the same key_person may reappear referencing a different person in the future.
key_retro: The person's Retrosheet identifier.
key_mlbam: The person's identifier as used by MLBAM (for example, in Gameday).
key_bbref: The person's identifier on Major League pages on baseball-reference.com.
key_bbref_minors: The person's identifier on minor league and Negro League pages on baseball-reference.com.
key_fangraphs: The person's identifier on fangraphs.com (Major Leaguers). As fangraphs uses BIS identifiers, this can also be used to match up people to BIS data.
key_npb: The person’s identifier on the NPB official site, npb.or.jp.
key_sr_nfl: The person's identifier on pro-football-reference.com
key_sr_nba: The person's identifier on basketball-reference.com
key_sr_nhl: The person's identifier on hockey-reference.com
key_findagrave: The identifier of the person's memorial on findagrave.com
"""


class Command(BaseCommand):
    def handle(self, *args, **options):

        with open('data/mlb_2_fg_cross.json', 'r') as readfile:
            players = json.loads(readfile.read())

            for p in players:
                try:
                    obj = models.Player.objects.get(fg_id=p['fg_id'])
                    obj.mlbam_id = p['mlbam_id']
                    obj.mlbam_checked = True
                    obj.save()

                except models.Player.MultipleObjectsReturned:
                    print(models.Player.objects.filter(fg_id=p['fg_id']))

                except models.Player.DoesNotExist:
                    pass