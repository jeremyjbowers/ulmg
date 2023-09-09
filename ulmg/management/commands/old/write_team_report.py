import csv
import ujson as json
import os
import datetime

from dateutil.parser import parse
from django.apps import apps
from django.db import connection
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError

from ulmg import models, utils


class Command(BaseCommand):
    teams = None
    strat_season = None
    required_pa = 550

    def hitter_report(self, team):
        def sorter(player, position):
            if position in ["CF", "SS", "2B"]:
                if int(player['rating']) == 1:
                    return int(player['obtb_tot']) + 8 - 60
                
                if int(player['rating']) == 2:
                    return int(player['obtb_tot']) + 5 - 60

                if int(player['rating']) == 3:
                    return int(player['obtb_tot']) - 60

                if int(player['rating']) == 4:
                    return int(player['obtb_tot']) - 5 - 60

                return int(player['obtb_tot']) - 8 - 60

            else:
                if int(player['rating']) == 1:
                    return int(player['obtb_tot']) + 4 - 60
                
                if int(player['rating']) == 2:
                    return int(player['obtb_tot']) + 2 - 60

                if int(player['rating']) == 3:
                    return int(player['obtb_tot']) - 60

                if int(player['rating']) == 4:
                    return int(player['obtb_tot']) - 2 - 60

                return int(player['obtb_tot']) - 4 - 60

        hitters = models.Player.objects.filter(team=team, stats__current__year=self.strat_season, stats__current__type="majors").exclude(position="P")

        positions = {
            "C": {"total_pa": 0, "players": []},
            "1B": {"total_pa": 0, "players": []},
            "2B": {"total_pa": 0, "players": []},
            "3B": {"total_pa": 0, "players": []},
            "SS": {"total_pa": 0, "players": []},
            "LF": {"total_pa": 0, "players": []},
            "CF": {"total_pa": 0, "players": []},
            "RF": {"total_pa": 0, "players": []}
        }

        for h in hitters:
            if h.defense and h.strat_ratings:
                for p in h.defense:
                    try:
                        pos = p.split('-')[0]

                        positions[pos]['total_pa'] += h.stats['current']['plate_appearances']

                        stat_dict = {}
                        stat_dict['name'] = h.name
                        stat_dict['rating'] = p.split('-')[2]
                        stat_dict['pa'] = int(h.stats['current']['plate_appearances'])
                        stat_dict['unlimited'] = False
                        if stat_dict['pa'] > 550:
                            stat_dict['unlimited'] = True
                        stat_dict['obtb_l'] = int(h.strat_ratings['current']['obtb_l'])
                        stat_dict['obtb_r'] = int(h.strat_ratings['current']['obtb_r'])
                        stat_dict['obtb_tot'] = int(h.strat_ratings['current']['obtb_tot'])
                        stat_dict['rtg'] = sorter(stat_dict, pos)

                        positions[pos]['players'].append(stat_dict)
                    except:
                        pass

        for k,v in positions.items():
            v['players'] = sorted(v['players'], key=lambda x:x['rtg'], reverse=True)

        # do lineup checks?
        lineup_order = ["C","CF","SS","2B","3B","RF","LF","1B","DH"]

        lineup = {
            "C": {"players": []},
            "CF": {"players": []},
            "SS": {"players": []},
            "2B": {"players": []},
            "3B": {"players": []},
            "LF": {"players": []},
            "1B": {"players": []},
            "DH": {"players": []}
        }

        for pos in lineup_order:

            # loop over all hitters qualified at that position, they're already sorted by rtg
            
            # 




    def handle(self, *args, **options):
        self.teams = models.Team.objects.all()
        self.strat_season = utils.get_ulmg_season(datetime.datetime.today()) - 1

        for t in self.teams:
            self.hitter_report(t)
