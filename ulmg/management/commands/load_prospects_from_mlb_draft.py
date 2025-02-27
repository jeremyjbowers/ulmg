from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from django.db.models import Count

from bs4 import BeautifulSoup
import requests
import ujson as json

from ulmg import models, utils

import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class Command(BaseCommand):

    def handle(self, *args, **options):
        def fix_pos(pos_string):
            
            if pos_string.lower().strip() == "c":
                return "C"

            if "p" in pos_string.lower().strip():
                return "P"

            if "b" in pos_string.lower().strip():
                return "IF"

            if "ss" in pos_string.lower().strip():
                return "IF"

            return "OF"

        def get_draft_json():
            r = requests.get('https://www.mlb.com/milb/prospects/draft/', verify=False)
            soup = BeautifulSoup(r.text, "html.parser")
            row_json = json.loads(soup.select('span')[34]['data-init-state'])

            with open('data/2025/mlb_draft_prospects.json', 'w') as writefile:
                writefile.write(json.dumps(row_json))

        def load_draft_json():
            with open('data/2025/mlb_draft_prospects.json', 'r') as readfile:
                row_json = json.loads(readfile.read())

                rows = [v for k,v in row_json['payload'].items() if "Person:" in k]
                for idx, row in enumerate(rows):
                    player_dict = {
                        "birthdate": row['birthDate'],
                        "name": f"{row['useName']} {row['useLastName']}",
                        "mlbam_id": row['id'],
                        "position": fix_pos(row['primaryPosition']['abbreviation'])
                    }
                    obj = None
                    try:
                        obj = models.Player.objects.get(mlbam_id=player_dict['mlbam_id'])
                    
                    except:
                        objs = models.Player.objects.filter(name=player_dict['name'])
                        if len(objs) == 1:
                            obj = objs[0]

                    if not obj:
                        obj = models.Player(**player_dict)

                    obj.level = "B"
                    for k,v in player_dict.items():
                        setattr(obj,k,v)

                    obj.save()
                    print(obj)

        load_draft_json()