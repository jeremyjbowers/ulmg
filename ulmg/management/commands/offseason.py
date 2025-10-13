import csv
import ujson as json
import os

from dateutil.parser import parse
from django.apps import apps
from django.db import connection
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Count, Avg, Sum, Max, Min, Q
from django.conf import settings

from ulmg import models, utils


class Command(BaseCommand):
    def set_carded(self, *args, **options):
        season = utils.get_current_season()

        if not options.get("dry_run", None):
            # Reset carded status in PlayerStatSeason for the season
            models.PlayerStatSeason.objects.filter(season=season).update(carded=False)
            
            # Set carded=True for players with MLB stats in that season
            models.PlayerStatSeason.objects.filter(
                season=season,
                classification="1-mlb",
                hit_stats__isnull=False
            ).update(carded=True)
            
            models.PlayerStatSeason.objects.filter(
                season=season,
                classification="1-mlb",
                pitch_stats__isnull=False
            ).update(carded=True)
        else:
            print(models.PlayerStatSeason.objects.filter(season=season).count())


    def reset_rosters(self, *args, **options):
        if not options.get("dry_run", None):
            # Reset Player model roster statuses that are still there
            models.Player.objects.filter(is_ulmg_1h_c=True).update(is_ulmg_1h_c=False)
            models.Player.objects.filter(is_ulmg_1h_p=True).update(is_ulmg_1h_p=False)
            models.Player.objects.filter(is_ulmg_1h_pos=True).update(is_ulmg_1h_pos=False)
            models.Player.objects.filter(is_ulmg_reserve=True).update(is_ulmg_reserve=False)

            models.Player.objects.filter(is_ulmg_2h_c=True).update(is_ulmg_2h_c=False)
            models.Player.objects.filter(is_ulmg_2h_p=True).update(is_ulmg_2h_p=False)
            models.Player.objects.filter(is_ulmg_2h_pos=True).update(is_ulmg_2h_pos=False)
            models.Player.objects.filter(is_ulmg_2h_draft=True).update(is_ulmg_2h_draft=False)

            # Reset PlayerStatSeason roster statuses for current season
            season = utils.get_current_season()
            models.PlayerStatSeason.objects.filter(season=season).update(
                is_ulmg_mlb_roster=False,
                is_ulmg_aaa_roster=False,
                is_ulmg35man_roster=False
            )

            # Unprotect all V and A players prior to the 35-man roster.
            models.Player.objects.filter(is_owned=True, level__in=["A", "V"]).update(
                is_ulmg_protected=False
            )
            
            # Get non-carded players for protection logic
            non_carded_player_ids = models.PlayerStatSeason.objects.filter(
                season=season,
                carded=False
            ).values_list('player_id', flat=True)
            
            models.Player.objects.filter(
                is_owned=True, 
                level__in=["A", "V"],
                id__in=non_carded_player_ids
            ).update(is_ulmg_protected=True)


    def load_career_hit(self, *args, **options):
        """
        https://www.fangraphs.com/leaders-legacy.aspx?pos=all&stats=bat&lg=all&qual=250&type=8&season=2025&month=0&season1=2000&ind=0&team=0&rost=0&age=&filter=&players=0&startdate=&enddate=&page=1_5000
        """

        hostname = utils.get_hostname()
        scriptname = utils.get_scriptname()
        timestamp = utils.generate_timestamp()

        print(f"{timestamp}\tcareer\tload_career_hit")

        # Reset existing career rows to avoid stale or mis-mapped data
        if not options.get("dry_run", None):
            models.PlayerStatSeason.objects.filter(is_career=True, classification="1-mlb").delete()

        updated = 0
        with open("data/career/hit.csv", "r") as readfile:
            players = csv.DictReader(readfile)
            for row in [dict(z) for z in players]:
                try:
                    player_obj = None
                    fg_id = (row.get("playerid") or "").strip()
                    mlbam_id = (row.get("mlbamid") or "").strip()
                    if fg_id:
                        try:
                            player_obj = models.Player.objects.get(fg_id=fg_id)
                        except models.Player.DoesNotExist:
                            player_obj = None
                    if not player_obj and mlbam_id:
                        try:
                            player_obj = models.Player.objects.get(mlbam_id=mlbam_id)
                        except models.Player.DoesNotExist:
                            player_obj = None
                    if not player_obj:
                        continue
                    p = player_obj
                    # Only load career MLB if the player already has an MLB stat season (handles legacy labels)
                    has_mlb = models.PlayerStatSeason.objects.filter(
                        player=p,
                        classification__in=["1-mlb", "1-majors"],
                    ).exists()
                    if not has_mlb:
                        continue
                    # Upsert a career PlayerStatSeason (MLB classification)
                    pss, _ = models.PlayerStatSeason.objects.get_or_create(
                        player=p,
                        classification="1-mlb",
                        is_career=True,
                        defaults={"season": None},
                    )
                    # Initialize or update hitting stats
                    hit_stats = pss.hit_stats or {}
                    # Minimum fields needed for level calculations
                    if "PA" in row and row["PA"]:
                        try:
                            hit_stats["pa"] = int(row["PA"])
                        except Exception:
                            pass
                    if "G" in row and row["G"]:
                        try:
                            hit_stats["g"] = int(row["G"])
                        except Exception:
                            pass
                    pss.hit_stats = hit_stats or None
                    if not options.get("dry_run", None):
                        pss.save()
                        updated += 1

                except:
                    pass
        print(f"career hitters updated: {updated}")


    def load_career_pitch(self, *args, **options):
        """
        https://www.fangraphs.com/leaders-legacy.aspx?pos=all&stats=pit&lg=all&qual=30&type=8&season=2025&month=0&season1=2000&ind=0&team=0&rost=0&age=0&filter=&players=0&startdate=&enddate=&page=1_5000
        """

        hostname = utils.get_hostname()
        scriptname = utils.get_scriptname()
        timestamp = utils.generate_timestamp()

        print(f"{timestamp}\tcareer\tload_career_pitch")

        updated = 0
        with open("data/career/pitch.csv", "r") as readfile:
            players = csv.DictReader(readfile)
            for row in [dict(z) for z in players]:
                try:
                    player_obj = None
                    fg_id = (row.get("playerid") or "").strip()
                    mlbam_id = (row.get("mlbamid") or "").strip()
                    if fg_id:
                        try:
                            player_obj = models.Player.objects.get(fg_id=fg_id)
                        except models.Player.DoesNotExist:
                            player_obj = None
                    if not player_obj and mlbam_id:
                        try:
                            player_obj = models.Player.objects.get(mlbam_id=mlbam_id)
                        except models.Player.DoesNotExist:
                            player_obj = None
                    if not player_obj:
                        continue
                    p = player_obj
                    # Only load career MLB if the player already has an MLB stat season (handles legacy labels)
                    has_mlb = models.PlayerStatSeason.objects.filter(
                        player=p,
                        classification__in=["1-mlb", "1-majors"],
                    ).exists()
                    if not has_mlb:
                        continue
                    # Upsert a career PlayerStatSeason (MLB classification)
                    pss, _ = models.PlayerStatSeason.objects.get_or_create(
                        player=p,
                        classification="1-mlb",
                        is_career=True,
                        defaults={"season": None},
                    )
                    pitch_stats = pss.pitch_stats or {}
                    if "GS" in row and row["GS"]:
                        try:
                            pitch_stats["gs"] = int(row["GS"])
                        except Exception:
                            pass
                    if "G" in row and row["G"]:
                        try:
                            pitch_stats["g"] = int(row["G"])
                        except Exception:
                            pass
                    if "IP" in row and row["IP"]:
                        try:
                            pitch_stats["ip"] = int(str(row["IP"]).split(".")[0])
                        except Exception:
                            pass
                    pss.pitch_stats = pitch_stats or None
                    if not options.get("dry_run", None):
                        pss.save()
                        updated += 1

                except:
                    pass
        print(f"career pitchers updated: {updated}")


    def set_levels(self, *args, **options):
        print("--------- STARTERS B > A ---------")
        starter_ids = models.PlayerStatSeason.objects.filter(
            is_career=True,
            classification="1-mlb",
            pitch_stats__gs__gte=21,
        ).values_list("player_id", flat=True)
        for p in models.Player.objects.filter(level="B", position="P", id__in=starter_ids):
            p.level = "A"
            print(p)
            if not options.get("dry_run", None):
                p.save()

        print("--------- RELIEVERS B > A ---------")
        reliever_ids = models.PlayerStatSeason.objects.filter(
            is_career=True,
            classification="1-mlb",
            pitch_stats__g__gte=31,
        ).values_list("player_id", flat=True)
        for p in models.Player.objects.filter(level="B", position="P", id__in=reliever_ids):
            p.level = "A"
            print(p)
            if not options.get("dry_run", None):
                p.save()
        print("--------- SWINGMEN B > A ---------")
        swingmen_ids = models.PlayerStatSeason.objects.filter(
            is_career=True,
            classification="1-mlb",
            pitch_stats__g__gte=40,
            pitch_stats__gs__gte=15,
        ).values_list("player_id", flat=True)
        for p in models.Player.objects.filter(level="B", position="P", id__in=swingmen_ids):
            p.level = "A"
            print(p)
            if not options.get("dry_run", None):
                p.save()

        print("--------- HITTERS B > A ---------")
        hitter_ids = models.PlayerStatSeason.objects.filter(
            is_career=True,
            classification="1-mlb",
            hit_stats__pa__gte=300,
        ).values_list("player_id", flat=True)
        for p in models.Player.objects.filter(level="B").exclude(position="P").filter(id__in=hitter_ids):
            p.level = "A"
            print(p)
            if not options.get("dry_run", None):
                p.save()

        print("--------- STARTERS A > V ---------")
        starter_ids = models.PlayerStatSeason.objects.filter(
            is_career=True,
            classification="1-mlb",
            pitch_stats__gs__gte=126,
        ).values_list("player_id", flat=True)
        for p in models.Player.objects.filter(level="A", position="P", id__in=starter_ids):
            p.level = "V"
            print(p)
            if not options.get("dry_run", None):
                p.save()

        print("--------- RELIEVERS A > V ---------")
        reliever_ids = models.PlayerStatSeason.objects.filter(
            is_career=True,
            classification="1-mlb",
            pitch_stats__g__gte=201,
        ).values_list("player_id", flat=True)
        for p in models.Player.objects.filter(level="A", position="P", id__in=reliever_ids):
            p.level = "V"
            print(p)
            if not options.get("dry_run", None):
                p.save()

        print("--------- SWINGMEN A > V ---------")
        swingmen_ids = models.PlayerStatSeason.objects.filter(
            is_career=True,
            classification="1-mlb",
            pitch_stats__g__gte=220,
            pitch_stats__gs__gte=30,
        ).values_list("player_id", flat=True)
        for p in models.Player.objects.filter(level="A", position="P", id__in=swingmen_ids):
            p.level = "V"
            print(p)
            if not options.get("dry_run", None):
                p.save()

        print("--------- HITTERS A > V ---------")
        hitter_ids = models.PlayerStatSeason.objects.filter(
            is_career=True,
            classification="1-mlb",
            hit_stats__pa__gte=2500,
        ).values_list("player_id", flat=True)
        for p in models.Player.objects.filter(level="A").exclude(position="P").filter(id__in=hitter_ids):
            p.level = "V"
            print(p)
            if not options.get("dry_run", None):
                p.save()



    def handle(self, *args, **options):
        self.set_carded()
        self.load_career_hit()
        self.load_career_pitch()
        self.set_levels()
        self.reset_rosters()

