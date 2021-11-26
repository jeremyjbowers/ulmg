from django.core.management.base import BaseCommand, CommandError

from ulmg import models, utils

class Command(BaseCommand):
    def handle(self, *args, **options):

        hostname = utils.get_hostname()
        scriptname = utils.get_scriptname()
        timestamp = utils.generate_timestamp()
        season = 2020

        for obj in models.Player.objects.filter(py_is_mlb=True, py_ab__gte=1):

            stats_dict = {}

            stats_dict['year'] = season
            stats_dict['type'] = "strat-imagined"
            stats_dict['timestamp'] = timestamp
            stats_dict['level'] = "mlb"
            stats_dict['side'] = "hit"
            stats_dict['script'] = scriptname
            stats_dict['host'] = hostname
            stats_dict['slug'] = f"{stats_dict['year']}-{stats_dict['type']}"

            stats_dict['hits'] = obj.py_hits
            stats_dict['2b'] = obj.py_2b
            stats_dict['3b'] = obj.py_3b
            stats_dict['ab'] = obj.py_ab
            stats_dict['hr'] = obj.py_hr
            stats_dict['sb'] = obj.py_sb
            stats_dict['runs'] = obj.py_runs
            stats_dict['rbi'] = obj.py_rbi
            stats_dict['k'] = obj.py_k
            stats_dict['bb'] = obj.py_bb
            stats_dict['avg'] = utils.to_float(obj.py_avg)
            stats_dict['obp'] = utils.to_float(obj.py_obp)
            stats_dict['slg'] = utils.to_float(obj.py_slg)
            stats_dict['babip'] = utils.to_float(obj.py_babip)
            stats_dict['wrc_plus'] = utils.to_float(obj.py_wrc_plus)
            stats_dict['plate_appearances'] = obj.py_plate_appearances
            stats_dict['iso'] = utils.to_float(obj.py_iso)
            stats_dict['k_pct'] = utils.to_float(obj.py_k_pct)
            stats_dict['bb_pct'] = utils.to_float(obj.py_bb_pct)

            obj.set_stats(stats_dict)
            obj.save()

        for obj in models.Player.objects.filter(py_is_mlb=True, py_g__gte=1):

            stats_dict = {}

            stats_dict['year'] = season
            stats_dict['type'] = "strat-imagined"
            stats_dict['timestamp'] = timestamp
            stats_dict['level'] = "mlb"
            stats_dict['side'] = "pitch"
            stats_dict['script'] = scriptname
            stats_dict['host'] = hostname
            stats_dict['slug'] = f"{stats_dict['year']}-{stats_dict['type']}"

            stats_dict['g'] = obj.py_g
            stats_dict['gs'] = obj.py_gs
            stats_dict['ip'] = obj.py_ip
            stats_dict['pk'] = obj.py_pk
            stats_dict['pbb'] = obj.py_pbb
            stats_dict['ha'] = obj.py_ha
            stats_dict['hra'] = obj.py_hra
            stats_dict['er'] = obj.py_er
            stats_dict['k_9'] = utils.to_float(obj.py_k_9)
            stats_dict['bb_9'] = utils.to_float(obj.py_bb_9)
            stats_dict['hr_9'] = utils.to_float(obj.py_hr_9)
            stats_dict['lob_pct'] = utils.to_float(obj.py_lob_pct)
            stats_dict['gb_pct'] = utils.to_float(obj.py_gb_pct)
            stats_dict['hr_fb'] = utils.to_float(obj.py_hr_fb)
            stats_dict['era'] = utils.to_float(obj.py_era)

            obj.set_stats(stats_dict)
            obj.save()