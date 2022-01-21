import csv
import json
import os
import shutil
import time

from django.core.management.base import BaseCommand, CommandError

from ulmg import models, utils


class Command(BaseCommand):
    def handle(self, *args, **options):
        # hitter_sheet = "1Enmoqo6dgpFrP-IpEZbvIeDYrMwHLME2i0X3E8Z6dj8"
        # hitter_range = "a1:z1000"
        # pitcher_sheet = ""

        # hitters = utils.get_sheet(hitter_sheet, hitter_range)

        # with open('data/2022/strat_card_ratings_hitter.json', 'w') as writefile:
        #     writefile.write(json.dumps(hitters))

        with open('data/2022/strat_card_ratings_hitter.json', 'r') as readfile:
            hitters = json.loads(readfile.read())

        def get_hitter(hitter):
            name_frag = hitter['player'].split(',')
            last = name_frag[0].strip().replace('*', '').replace('+', '')
            first = name_frag[1].strip().replace('*', '').replace('+', '')

            if hitter['ulmg_id'].strip() != "":
                return utils.strat_find_player(first, last, ulmg_id=hitter['ulmg_id'])

            return utils.strat_find_player(first, last, hitter=True, mlb_team_abbr=hitter['tm'])


        for h in hitters:
            p = get_hitter(h)
            for f in ['obtb', 'ob', 'h', 'hr', 'tb', 'bb', 'so']:
                for hand in ['l', 'r']:
                    setattr(p, f"strat_{f}_{hand}", h[f"{f}_{hand}"])
            p.save()
