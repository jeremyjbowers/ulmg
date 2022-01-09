import json
import time
import csv

from bs4 import BeautifulSoup
from django.core.management.base import BaseCommand, CommandError
import requests

from ulmg import models


class Command(BaseCommand):
    def handle(self, *args, **options):
        draft = []

        with open("data/2022/ftrax_2022_draft.html", "r") as readfile:
            soup = BeautifulSoup(readfile.read(), "lxml")
            rows = soup.select("table.draftGrid tr")[1:]

            for rnd, row in enumerate(rows):
                rnd = rnd + 1

                for pick, cell in enumerate(row.select("td")[1:]):
                    pick = pick + 1
                    name = cell.select("a")[0].text.strip()
                    team = cell.select("div > div")[0].text.split(" (")[0].strip()
                    pos = (
                        cell.select("div > div")[0]
                        .text.split(" (")[1]
                        .split(")")[0]
                        .strip()
                    )

                    payload = {
                        "pick": pick,
                        "round": rnd,
                        "player": name,
                        "team": team,
                        "position": pos,
                    }
                    draft.append(payload)

        with open("data/2022/ftrax_2022_draft.json", "w") as writefile:
            writefile.write(json.dumps(draft))

        with open("data/2022/ftrax_2022_draft.csv", "w") as writefile:
            fieldnames = draft[0].keys()
            writer = csv.DictWriter(writefile, fieldnames=fieldnames)
            writer.writeheader()

            for pick in draft:
                writer.writerow(pick)
