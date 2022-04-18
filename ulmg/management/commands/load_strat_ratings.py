import csv
import json
import os
import shutil
import time

from django.core.management.base import BaseCommand, CommandError

from ulmg import models, utils


class Command(BaseCommand):
    def handle(self, *args, **options):
        self.get_pitcher_data()
        self.load_pitchers()

        # self.get_hitter_data()
        # self.load_hitters()

    def get_player(self, player, hitter=True):
        name_frag = player["player"].split(",")
        last = name_frag[0].strip().replace("*", "").replace("+", "")
        first = name_frag[1].strip().replace("*", "").replace("+", "")

        if player["ulmg_id"].strip() != "":
            return utils.strat_find_player(first, last, ulmg_id=player["ulmg_id"])

        return utils.strat_find_player(
            first, last, hitter=hitter, mlb_team_abbr=player["tm"]
        )

    def get_pitcher_data(self, fresh=False):
        if fresh:
            os.system("rm -rf data/2022/strat_card_ratings_pitcher.json")

        if not os.path.isfile("data/2022/strat_card_ratings_pitcher.json"):
            pitcher_sheet = "1NvSGtcSyReCiu8h9DPcm1ShYGCuzxucCzRIsXH6XOp4"
            pitcher_range = "A:R"

            pitchers = utils.get_sheet(pitcher_sheet, pitcher_range)

            with open("data/2022/strat_card_ratings_pitcher.json", "w") as writefile:
                writefile.write(json.dumps(pitchers))

    def get_hitter_data(self, fresh=False):
        if fresh:
            os.system("rm -rf data/2022/strat_card_ratings_hitter.json")

        if not os.path.isfile("data/2022/strat_card_ratings_hitter.json"):
            hitter_sheet = "1Enmoqo6dgpFrP-IpEZbvIeDYrMwHLME2i0X3E8Z6dj8"
            hitter_range = "a1:z1000"

            hitters = utils.get_sheet(hitter_sheet, hitter_range)

            with open("data/2022/strat_card_ratings_hitter.json", "w") as writefile:
                writefile.write(json.dumps(hitters))

    def load_hitters(self, save=True):
        with open("data/2022/strat_card_ratings_hitter.json", "r") as readfile:
            hitters = json.loads(readfile.read())

        for h in hitters:
            p = self.get_player(h)
            for f in ["obtb", "ob", "h", "hr", "tb", "bb", "so"]:
                for hand in ["l", "r"]:
                    setattr(p, f"strat_{f}_{hand}", h[f"{f}_{hand}"])
            print(p)

            if save:
                p.save()

    def load_pitchers(self, save=True):
        with open("data/2022/strat_card_ratings_pitcher.json", "r") as readfile:
            pitchers = json.loads(readfile.read())

        for h in pitchers:
            p = self.get_player(h, hitter=False)
            if p:
                for f in ["obtb", "ob", "h", "hr", "tb", "bb", "so"]:
                    for hand in ["l", "r"]:
                        setattr(p, f"strat_p_{f}_{hand}", h[f"{f}_{hand}"])
            else:
                print(f"{h['tm']}\t{h['player']}")

            if save:
                p.save()
