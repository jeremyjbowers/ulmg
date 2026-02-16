# ABOUTME: ARCHIVED - Original live_download_mlb_depthcharts. See documents/MLB_DATA_PIPELINE_RECOMMENDATION.md
# ABOUTME: Hits MLB Stats API for 40-man rosters, updates existing players, writes untracked to untracked_players.json.
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from django.db import transaction
import datetime

import requests
from bs4 import BeautifulSoup
import ujson as json

from ulmg import models, utils


class Command(BaseCommand):
    mlb_lookup = {
        "108": "LAA",
        "109": "AZ",
        "110": "BAL",
        "111": "BOS",
        "112": "CHC",
        "113": "CIN",
        "114": "CLE",
        "115": "COL",
        "116": "DET",
        "117": "HOU",
        "118": "KC",
        "119": "LAD",
        "120": "WSH",
        "121": "NYM",
        "133": "ATH",
        "134": "PIT",
        "135": "SD",
        "136": "SEA",
        "137": "SF",
        "138": "STL",
        "139": "TB",
        "140": "TEX",
        "141": "TOR",
        "142": "MIN",
        "143": "PHI",
        "144": "ATL",
        "145": "CWS",
        "146": "MIA",
        "147": "NYY",
        "158": "MIL",
    }

    def get_rosters(self):
        current_season = datetime.datetime.now().year

        models.PlayerStatSeason.objects.filter(season=current_season).update(roster_status="MINORS")

        team_list_url = "https://statsapi.mlb.com/api/v1/teams/"
        r = requests.get(team_list_url)
        team_list = r.json()['teams']

        mlb_teams = [self.parse_players(t) for t in team_list if t['sport']['id'] == 1]
        aaa_teams = [self.parse_players(t) for t in team_list if t['sport']['id'] == 11]
        aa_teams = [self.parse_players(t) for t in team_list if t['sport']['id'] == 12]
        high_a_teams = [self.parse_players(t) for t in team_list if t['sport']['id'] == 13]
        a_teams = [self.parse_players(t) for t in team_list if t['sport']['id'] == 14]
        ss_a_teams = [self.parse_players(t) for t in team_list if t['sport']['id'] == 15]
        rookie_teams = [self.parse_players(t) for t in team_list if t['sport']['id'] == 16]

    def parse_players(self, t):
        current_season = settings.CURRENT_SEASON
        roster_link = f"https://statsapi.mlb.com/api/v1/teams/{t['id']}/roster/40Man"
        tr = requests.get(roster_link).json()

        if tr.get('roster', None):
            if t['sport']['id'] != 1:
                try:
                    mlb_team = self.mlb_lookup[str(t['parentOrgId'])]
                except Exception:
                    pass
            else:
                mlb_team = t['abbreviation']

            for p in tr['roster']:
                player_dict = {}
                player_dict['mlbam_id'] = p['person']['id']
                player_dict['name'] = p['person']['fullName']
                player_dict['position'] = utils.normalize_pos(p['position']['abbreviation'])
                player_dict['mlb_org'] = mlb_team
                player_dict['roster_status'] = "MINORS"

                if "injured" in p['status']['description'].lower():
                    if "7" in p['status']['description']:
                        player_dict['roster_status'] = "IL-7"
                    if "10" in p['status']['description']:
                        player_dict['roster_status'] = "IL-10"
                    if "15" in p['status']['description']:
                        player_dict['roster_status'] = "IL-15"
                    if "60" in p['status']['description']:
                        player_dict['roster_status'] = "IL-60"

                if t['sport']['id'] == 1:
                    if 'active' in p['status']['description'].lower():
                        player_dict['roster_status'] = "MLB"

                try:
                    player_obj = models.Player.objects.get(mlbam_id=player_dict['mlbam_id'])
                    if player_dict.get('name'):
                        player_obj.name = player_dict['name']
                    if player_dict.get('position'):
                        player_obj.position = player_dict['position']
                    if player_dict.get('mlb_org'):
                        player_obj.current_mlb_org = player_dict['mlb_org']
                    if player_dict.get('roster_status'):
                        player_obj.current_mlb_roster_status = player_dict['roster_status']
                    player_obj.save()

                    with transaction.atomic():
                        player_stat_season, created = models.PlayerStatSeason.objects.get_or_create(
                            player=player_obj,
                            season=current_season,
                            classification='1-mlb',
                            defaults={
                                'mlb_org': player_dict['mlb_org'],
                                'roster_status': player_dict['roster_status']
                            }
                        )
                        if not created:
                            player_stat_season.mlb_org = player_dict['mlb_org']
                            player_stat_season.roster_status = player_dict['roster_status']
                            player_stat_season.save()

                except models.Player.DoesNotExist:
                    try:
                        if not hasattr(self, 'untracked_players'):
                            self.untracked_players = []
                        self.untracked_players.append(player_dict)
                    except Exception:
                        pass

    def fix_bad_player_ids(self):
        bad_ids = models.Player.objects.filter(mlbam_id__icontains="/")
        bad_ids.delete()

    def handle(self, *args, **options):
        self.untracked_players = []
        self.fix_bad_player_ids()
        self.get_rosters()
        try:
            if self.untracked_players:
                with open('data/rosters/untracked_players.json', 'w') as writefile:
                    writefile.write(json.dumps(self.untracked_players))
        except Exception:
            pass
