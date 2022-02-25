import csv
import json
import os
from decimal import Decimal

from dateutil.parser import parse
from django.apps import apps
from django.db import connection
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from nameparser import HumanName

from ulmg import models
from ulmg import utils


class Command(BaseCommand):
    # if you have data and want to run this for a previous season, here is how you'd do it.
    # you'd want to make sure not to grab new data.
    season = 2022

    # the sheets where the top 100 and top draft are collated.
    top_100_filename = f"data/{season}/top_100_prospects.json"
    top_100_sheet = "1Wb9f6QrGULjg2qs2Bmq6EWVXXKmw-WdYg-loYvGnpFY"
    top_100_range = "top_100!A:N"
    top_draft_sheet = "1Wb9f6QrGULjg2qs2Bmq6EWVXXKmw-WdYg-loYvGnpFY"
    top_draft_filename = f"data/{season}/top_draft_prospects.json"
    top_draft_range = "top_draft!A:L"

    file_map = {
        "top-100": top_100_filename,
        "top-draft": top_draft_filename
    }

    def handle(self, *args, **options):
        # These two commands make the script more or less idempotent.
        # Generally, I want this sort of thing to:
        # (a) clean up ahead of what it plans to modify
        # (b) do the modifications such that it won't create duplicates

        # (1) Remove all previous runs of this script because it should be fresh. Leave previous years.
        models.ProspectRating.objects.filter(year=self.season).delete()

        # (2) Clear out prospect status. This is distinct from is_minors. We'll set this soon.
        models.Player.objects.update(is_prospect=False)

        # Get data files
        self.get_top_draft_data(fresh=False)
        self.get_top_100_data(fresh=False)

        self.load_top_100()
        self.load_top_draft()

        # denormalize all the wishlist players to get access to scouting data
        for s in models.WishlistPlayer.objects.all():
            s.save()

    def get_top_draft_data(self, fresh=False):
        """
        Gets data for draft prospects from a Google sheet.
        Only grabs it new if fresh=True is set.
        """
        if fresh:
            os.system(f'rm -rf {self.top_draft_filename}')

        if not os.path.isfile(self.top_draft_filename):
            players = utils.get_sheet(self.top_draft_sheet, self.top_draft_range)

            with open(self.top_draft_filename, 'w') as writefile:
                writefile.write(json.dumps(players))

    def get_top_100_data(self, fresh=False):
        """
        Gets data for top 100 prospects from a Google sheet.
        Only grabs it new if fresh=True is set.
        """
        if fresh:
            os.system(f'rm -rf {self.top_100_filename}')

        if not os.path.isfile(self.top_100_filename):
            players = utils.get_sheet(self.top_100_sheet, self.top_100_range)

            with open(self.top_100_filename, 'w') as writefile:
                writefile.write(json.dumps(players)) 

    def load_top_draft(self, save=True):
        rank_type = "top-draft"
        filename = self.file_map[rank_type]

        with open(self.top_draft_filename, "r") as readfile:
            players = json.loads(readfile.read())

        for row in players:
            pr, created = self.get_player_and_rating(row, rank_type)
            pr.avg = row["avg"]
            pr.med = row["med"]
            pr.mlb = utils.int_or_none(row["mlb"])
            pr.ba = utils.int_or_none(row["ba"])
            pr.plive = utils.int_or_none(row["plive"])
            pr.espn = utils.int_or_none(row["espn"])
            pr.law = utils.int_or_none(row["law"])
            pr.p365 = utils.int_or_none(row["p365"])
            pr.fg = utils.int_or_none(row["fg"])
            pr.cbs = utils.int_or_none(row["cbs"])

            if save:
                pr.save()
                print(pr)

    def load_top_100(self, save=True):
        rank_type = "top-100"
        filename = self.file_map[rank_type]

        with open(filename, "r") as readfile:
            players = json.loads(readfile.read())

        for row in players:
            pr, created = self.get_player_and_rating(row, rank_type)
            pr.avg = row["avg"]
            pr.med = row["med"]
            pr.mlb = utils.int_or_none(row["mlb"])
            pr.ba = utils.int_or_none(row["ba"])
            pr.bp = utils.int_or_none(row["bp"])
            pr.law = utils.int_or_none(row["law"])
            pr.fg = utils.int_or_none(row["fg"])
            pr.espn = utils.int_or_none(row["espn"])
            pr.plive = utils.int_or_none(row["plive"])
            pr.ftrax = utils.int_or_none(row["ftrax"])

            if save:
                pr.save()
                print(pr.fg)

    def get_player_and_rating(self, row, rank_type):
        p = utils.fuzzy_find_player(row["player"])
        if len(p) > 0:
            p = p[0]
        else:
            p = None

        if p:
            p.is_prospect = True

            # This is denormalized onto the player.
            # Everything else is accessible via the associated ProspectRating.
            p.prospect_rating_avg = Decimal(row["avg"])
            p.save()

        return models.ProspectRating.objects.get_or_create(
            year=self.season, player=p, player_name=row["player"], rank_type=rank_type
        )  