import csv
import os

from django.apps import apps
from django.db import connection
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError

from ulmg import models
from ulmg import utils


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("year", type=str)

    def clear_defense(self):
        models.Player.objects.exclude(position="P").update(defense=[])

    def set_player_defense(self, player_row, obj, dry_run=False):
        if not obj.defense:
            obj.defense = []
        defense = set()
        for d in obj.defense:
            defense.add(d)
        for pos in [
            "C-2",
            "1B-3",
            "2B-4",
            "3B-5",
            "SS-6",
            "RF-9",
            "CF-8",
            "LF-7",
        ]:
            if player_row[pos.split("-")[0]] != "":
                rating = player_row[pos.split("-")[0]]
                if "(" in rating:
                    rating = rating.split("(")[0]
                d = f"{pos}-{rating}"
                defense.add(d)
        obj.defense = list(defense)
        inf = False
        of = False
        c = False

        for p in obj.defense:
            if "C-" in p:
                c = True
            if "F-" in p:
                of = True
            if "B-" in p:
                inf = True
            if "SS" in p:
                inf = True

            if inf == True:
                obj.position = "IF"

            if of == True:
                obj.position = "OF"

            if inf == True and of == True:
                obj.position = "IF-OF"

            if c == True:
                obj.position = "C"

        if obj.defense == []:
            obj.position = "DH"

        print(obj.name, obj.defense)
        if not dry_run:
            obj.save()

    def set_defense(self, year=None, dry_run=False):
        if year:
            with open(f"data/defense/{year}-som-range.csv", "r") as readfile:
                players = [dict(c) for c in csv.DictReader(readfile) if c["B/P"] == "B"]

                for player_row in players:
                    name_string = f"{player_row['FIRST']} {player_row['LAST']}"
                    fuzzy_players = utils.fuzzy_find_player(name_string)
                    if len(fuzzy_players) > 0:
                        self.set_player_defense(
                            player_row, fuzzy_players[0], dry_run=dry_run
                        )

        else:
            print(
                "Please pass a year along with the command, e.g., django-admin import_defense 2020"
            )

    def handle(self, *args, **options):
        year = options.get("year", None)

        self.clear_defense()
        self.set_defense(year=year, dry_run=False)
