import csv
import ujson as json

from django.core.management.base import BaseCommand, CommandError

from ulmg import utils


class Command(BaseCommand):
    def handle(self, *args, **options):
        with open("data/2022/ba_top_100_dynasty.csv", "r") as readfile:
            """
            rank,player,position,organization,age,prospect_rank
            """
            payload = []
            players = csv.DictReader(readfile)
            for p in players:
                obj = utils.fuzzy_find_player(p["player"])
                if len(obj) == 1:
                    obj = obj[0]
                    if not obj.is_owned:
                        p["player_id"] = obj.id
                        p["ulmg_position"] = obj.position
                        p["ulmg_level"] = obj.level
                        payload.append(p)

            with open("data/2022/best_available.json", "w") as writefile:
                writefile.write(json.dumps(payload))
