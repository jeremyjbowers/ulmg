import csv
import json
import os

from bs4 import BeautifulSoup
from django.apps import apps
from django.db import connection
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError

from ulmg import models


class Command(BaseCommand):

    def handle(self, *args, **options):

        def write_csv(path, payload):
            with open(path, 'w') as csvfile:
                fieldnames = list(payload[0].keys())
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                for p in payload:
                    writer.writerow(p)

        def normalize_pos(pos):
            if pos.upper() in ["1B", "2B", "3B", "SS"]:
                pos = "IF"
            if pos.upper() in ["RF", "CF", "LF"]:
                pos = "OF"
            if "P" in pos.upper():
                pos = "P"
            return pos

        with open('data/mlb_draft/2019-pl-draft.html', 'r') as readfile:
            soup = BeautifulSoup(readfile.read(), 'lxml')
            players = soup.select('#block-ad9c042eb3db56291a08 div.sqs-block-content p')[3:]
            payload = []
            for p in players:
                if len(p.select('strong')) > 0:
                    p = p.select('strong')[0].text.strip()
                    print(p)
                    # p_dict = {}
                    # p_dict['name'] = p.select('.player-name')[0].text.strip()
                    # p_dict['mlb_rank'] = p.select('.number')[0].text.strip()
                    # p_dict['position'] = p.select('.player-info')[0].text.strip()
                    # payload.append(p_dict)

                # write_csv('data/mlb_draft/2019-mlb-draft.csv', payload)
