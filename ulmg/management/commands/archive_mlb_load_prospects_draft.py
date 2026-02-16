# ABOUTME: ARCHIVED - Original load_prospects_from_mlb_draft. See documents/MLB_DATA_PIPELINE_RECOMMENDATION.md
# ABOUTME: Scrapes mlb.com/milb/prospects/draft/ for draft prospects, writes data/2025/mlb_draft_prospects.json.
from django.core.management.base import BaseCommand
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
            if "b" in pos_string.lower().strip() or "ss" in pos_string.lower().strip():
                return "IF"
            return "OF"

        r = requests.get('https://www.mlb.com/milb/prospects/draft/', verify=False)
        soup = BeautifulSoup(r.text, "html.parser")
        row_json = json.loads(soup.select('span')[34]['data-init-state'])
        with open('data/2025/mlb_draft_prospects.json', 'w') as writefile:
            writefile.write(json.dumps(row_json))
        rows = [v for k, v in row_json['payload'].items() if "Person:" in k]
        for row in rows:
            player_dict = {
                "birthdate": row['birthDate'],
                "name": f"{row['useName']} {row['useLastName']}",
                "mlbam_id": row['id'],
                "position": fix_pos(row['primaryPosition']['abbreviation'])
            }
            obj = None
            try:
                obj = models.Player.objects.get(mlbam_id=player_dict['mlbam_id'])
            except models.Player.DoesNotExist:
                objs = models.Player.objects.filter(name=player_dict['name'])
                if len(objs) == 1:
                    obj = objs[0]
            if not obj:
                obj = models.Player(**player_dict)
            obj.level = "B"
            for k, v in player_dict.items():
                setattr(obj, k, v)
            obj.save()
