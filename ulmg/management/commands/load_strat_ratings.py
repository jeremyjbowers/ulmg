import csv
import json
import os
import shutil
import time
import datetime

from django.core.management.base import BaseCommand, CommandError

from ulmg import models, utils
# from scipy import stats

import warnings
warnings.filterwarnings("ignore")


class Command(BaseCommand):
    season = None
    hitters = None
    hitter_obtb_l = None
    hitter_obtb_r = None
    hitter_obtb_tot = None

    def handle(self, *args, **options):
        self.season = utils.get_strat_season() + 1
        self.load_hitters()

    def get_player(self, player, hitter=True):
        name_frag = player["player_1"].split(",")
        last = name_frag[0].strip().replace("*", "").replace("+", "")
        first = name_frag[1].strip().replace("*", "").replace("+", "")

        return utils.strat_find_player(
            first, last, hitter=hitter, mlb_team_abbr=player["tm"]
        )

    def load_hitters(self, save=True):
        with open(f"data/{self.season}/strat-hit.csv", "r") as readfile:
            self.hitters = [h for h in csv.DictReader(readfile)]

        self.hitter_obtb_l = [h['obtb_l'] for h in self.hitters]
        self.hitter_obtb_r = [h['obtb_r'] for h in self.hitters]
        self.hitter_obtb_tot = [h['tot'] for h in self.hitters]

        for h in self.hitters:
            p = self.get_player(h)
            if p:
                if not p.strat_ratings:
                    # get us an empty dict
                    p.strat_ratings = {}

                if not p.strat_ratings.get(self.season):
                    # get us a current season and this specific year updated
                    p.strat_ratings['current'] = {}
                    p.strat_ratings[self.season] = {}

                strat_dict = {}
                strat_dict['unlimited'] = False
                strat_dict['pa'] = int(h['pa'])

                if strat_dict['pa'] >= 550:
                    strat_dict['unlimited'] = True

                strat_dict['obtb_l'] = h['obtb_l']
                strat_dict['obtb_r'] = h['obtb_r']
                strat_dict['obtb_tot'] = h['tot']

                # strat_dict['obtb_l_ptile'] = stats.percentileofscore(self.hitter_obtb_l, h['obtb_l'], kind='strict')
                # strat_dict['obtb_r_ptile'] = stats.percentileofscore(self.hitter_obtb_r, h['obtb_r'], kind='strict')
                # strat_dict['obtb_tot_ptile'] = stats.percentileofscore(self.hitter_obtb_tot, h['tot'], kind='strict')

                p.strat_ratings['current'] = strat_dict
                p.strat_ratings[self.season] = strat_dict

                if save:
                    print(p)
                    p.save()

            else:
                print(h)