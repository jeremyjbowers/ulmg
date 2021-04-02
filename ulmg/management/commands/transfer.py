from django.core.management.base import BaseCommand, CommandError

from ulmg import models

class Command(BaseCommand):
    def handle(self, *args, **options):
        for obj in models.Player.objects.filter(ls_is_mlb=True):
            obj.py_is_mlb = obj.ls_is_mlb
            obj.py_hits = obj.ls_hits
            obj.py_2b = obj.ls_2b
            obj.py_3b = obj.ls_3b
            obj.py_ab = obj.ls_ab
            obj.py_hr = obj.ls_hr
            obj.py_sb = obj.ls_sb
            obj.py_runs = obj.ls_runs
            obj.py_rbi = obj.ls_rbi
            obj.py_k = obj.ls_k
            obj.py_bb = obj.ls_bb
            obj.py_avg = obj.ls_avg
            obj.py_obp = obj.ls_obp
            obj.py_slg = obj.ls_slg
            obj.py_babip = obj.ls_babip
            obj.py_wrc_plus = obj.ls_wrc_plus
            obj.py_plate_appearances = obj.ls_plate_appearances
            obj.py_iso = obj.ls_iso
            obj.py_k_pct = obj.ls_k_pct
            obj.py_bb_pct = obj.ls_bb_pct
            obj.py_woba = obj.ls_woba
            obj.py_g = obj.ls_g
            obj.py_gs = obj.ls_gs
            obj.py_ip = obj.ls_ip
            obj.py_pk = obj.ls_pk
            obj.py_pbb = obj.ls_pbb
            obj.py_ha = obj.ls_ha
            obj.py_hra = obj.ls_hra
            obj.py_er = obj.ls_er
            obj.py_k_9 = obj.ls_k_9
            obj.py_bb_9 = obj.ls_bb_9
            obj.py_hr_9 = obj.ls_hr_9
            obj.py_lob_pct = obj.ls_lob_pct
            obj.py_gb_pct = obj.ls_gb_pct
            obj.py_hr_fb = obj.ls_hr_fb
            obj.py_era = obj.ls_era
            obj.py_fip = obj.ls_fip
            obj.py_xfip = obj.ls_xfip
            obj.py_siera = obj.ls_siera
            obj.py_xavg = obj.ls_xavg
            obj.py_xwoba = obj.ls_xwoba
            obj.py_xslg = obj.ls_xslg
            obj.py_xavg_diff = obj.ls_xavg_diff
            obj.py_xwoba_diff = obj.ls_xwoba_diff
            obj.py_xslg_diff = obj.ls_xslg_diff
            obj.save()