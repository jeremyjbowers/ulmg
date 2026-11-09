# ABOUTME: Offseason maintenance: carded flags, career totals, level promotions, and roster reset.
# ABOUTME: --dry-run runs those steps, reports the difference, and rolls the transaction back.

import csv
import ujson as json
import os

from dateutil.parser import parse
from django.apps import apps
from django.db import connection, transaction
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Count, Avg, Sum, Max, Min, Q
from django.conf import settings

from ulmg import models, utils


HIT_CSV = "data/career/hit.csv"
PITCH_CSV = "data/career/pitch.csv"

PLAYER_FIELDS = [
    "id",
    "name",
    "level",
    "is_owned",
    "is_ulmg_protected",
    "is_ulmg_1h_c",
    "is_ulmg_1h_p",
    "is_ulmg_1h_pos",
    "is_ulmg_reserve",
    "is_ulmg_2h_c",
    "is_ulmg_2h_p",
    "is_ulmg_2h_pos",
    "is_ulmg_2h_draft",
    "is_ulmg_35man_roster",
    "is_ulmg_mlb_roster",
    "is_ulmg_aaa_roster",
]
PLAYER_FLAG_FIELDS = [
    "is_ulmg_1h_c",
    "is_ulmg_1h_p",
    "is_ulmg_1h_pos",
    "is_ulmg_reserve",
    "is_ulmg_2h_c",
    "is_ulmg_2h_p",
    "is_ulmg_2h_pos",
    "is_ulmg_2h_draft",
    "is_ulmg_35man_roster",
    "is_ulmg_mlb_roster",
    "is_ulmg_aaa_roster",
    "is_owned",
]
STAT_FIELDS = [
    "id",
    "player_id",
    "season",
    "is_career",
    "classification",
    "carded",
    "hit_stats",
    "pitch_stats",
    "roster_status",
    "mlb_org",
    "is_ulmg_mlb_roster",
    "is_ulmg_aaa_roster",
    "is_ulmg35man_roster",
]
STAT_ROSTER_FIELDS = [
    "roster_status",
    "mlb_org",
    "is_ulmg_mlb_roster",
    "is_ulmg_aaa_roster",
    "is_ulmg35man_roster",
]


class Command(BaseCommand):
    help = (
        "Set carded status, reload career hitting and pitching, promote levels, "
        "and reset rosters. --dry-run reports those changes and saves nothing."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would change, then roll the changes back.",
        )

    def set_carded(self, *args, **options):
        season = utils.get_current_season()

        # Reset carded status in PlayerStatSeason for the season
        models.PlayerStatSeason.objects.filter(season=season).update(carded=False)

        # Set carded=True for players with MLB appearances in that season
        models.PlayerStatSeason.objects.filter(
            season=season,
            classification="1-mlb",
        ).filter(utils.mlb_appearances_q()).update(carded=True)


    def reset_rosters(self, *args, **options):
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
            is_ulmg35man_roster=False,
            roster_status=None,
            mlb_org=None,
        )
        # Reset Player model 40-man roster so managers can set protections fresh
        models.Player.objects.filter(is_owned=True).update(
            is_ulmg_35man_roster=False,
            is_ulmg_mlb_roster=False,
            is_ulmg_aaa_roster=False,
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

        self.stdout.write(f"{timestamp}\tcareer\tload_career_hit")

        # Reset existing career rows to avoid stale or mis-mapped data
        models.PlayerStatSeason.objects.filter(is_career=True, classification="1-mlb").delete()

        updated = 0
        with open(HIT_CSV, "r") as readfile:
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
                    pss.save()
                    updated += 1

                except:
                    pass
        self.stdout.write(f"career hitters updated: {updated}")


    def load_career_pitch(self, *args, **options):
        """
        https://www.fangraphs.com/leaders-legacy.aspx?pos=all&stats=pit&lg=all&qual=30&type=8&season=2025&month=0&season1=2000&ind=0&team=0&rost=0&age=0&filter=&players=0&startdate=&enddate=&page=1_5000
        """

        hostname = utils.get_hostname()
        scriptname = utils.get_scriptname()
        timestamp = utils.generate_timestamp()

        self.stdout.write(f"{timestamp}\tcareer\tload_career_pitch")

        updated = 0
        with open(PITCH_CSV, "r") as readfile:
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
                    pss.save()
                    updated += 1

                except:
                    pass
        self.stdout.write(f"career pitchers updated: {updated}")


    def set_levels(self, *args, **options):
        self.stdout.write("--------- STARTERS B > A ---------")
        starter_ids = models.PlayerStatSeason.objects.filter(
            is_career=True,
            classification="1-mlb",
            pitch_stats__gs__gte=21,
        ).values_list("player_id", flat=True)
        for p in models.Player.objects.filter(level="B", position="P", id__in=starter_ids):
            p.level = "A"
            self.stdout.write(str(p))
            p.save()

        self.stdout.write("--------- RELIEVERS B > A ---------")
        reliever_ids = models.PlayerStatSeason.objects.filter(
            is_career=True,
            classification="1-mlb",
            pitch_stats__g__gte=31,
        ).values_list("player_id", flat=True)
        for p in models.Player.objects.filter(level="B", position="P", id__in=reliever_ids):
            p.level = "A"
            self.stdout.write(str(p))
            p.save()
        self.stdout.write("--------- SWINGMEN B > A ---------")
        swingmen_ids = models.PlayerStatSeason.objects.filter(
            is_career=True,
            classification="1-mlb",
            pitch_stats__g__gte=40,
            pitch_stats__gs__gte=15,
        ).values_list("player_id", flat=True)
        for p in models.Player.objects.filter(level="B", position="P", id__in=swingmen_ids):
            p.level = "A"
            self.stdout.write(str(p))
            p.save()

        self.stdout.write("--------- HITTERS B > A ---------")
        hitter_ids = models.PlayerStatSeason.objects.filter(
            is_career=True,
            classification="1-mlb",
            hit_stats__pa__gte=300,
        ).values_list("player_id", flat=True)
        for p in models.Player.objects.filter(level="B").exclude(position="P").filter(id__in=hitter_ids):
            p.level = "A"
            self.stdout.write(str(p))
            p.save()

        self.stdout.write("--------- STARTERS A > V ---------")
        starter_ids = models.PlayerStatSeason.objects.filter(
            is_career=True,
            classification="1-mlb",
            pitch_stats__gs__gte=126,
        ).values_list("player_id", flat=True)
        for p in models.Player.objects.filter(level="A", position="P", id__in=starter_ids):
            p.level = "V"
            self.stdout.write(str(p))
            p.save()

        self.stdout.write("--------- RELIEVERS A > V ---------")
        reliever_ids = models.PlayerStatSeason.objects.filter(
            is_career=True,
            classification="1-mlb",
            pitch_stats__g__gte=201,
        ).values_list("player_id", flat=True)
        for p in models.Player.objects.filter(level="A", position="P", id__in=reliever_ids):
            p.level = "V"
            self.stdout.write(str(p))
            p.save()

        self.stdout.write("--------- SWINGMEN A > V ---------")
        swingmen_ids = models.PlayerStatSeason.objects.filter(
            is_career=True,
            classification="1-mlb",
            pitch_stats__g__gte=220,
            pitch_stats__gs__gte=30,
        ).values_list("player_id", flat=True)
        for p in models.Player.objects.filter(level="A", position="P", id__in=swingmen_ids):
            p.level = "V"
            self.stdout.write(str(p))
            p.save()

        self.stdout.write("--------- HITTERS A > V ---------")
        hitter_ids = models.PlayerStatSeason.objects.filter(
            is_career=True,
            classification="1-mlb",
            hit_stats__pa__gte=2500,
        ).values_list("player_id", flat=True)
        for p in models.Player.objects.filter(level="A").exclude(position="P").filter(id__in=hitter_ids):
            p.level = "V"
            self.stdout.write(str(p))
            p.save()

    def _execute(self):
        self.set_carded()
        self.load_career_hit()
        self.load_career_pitch()
        self.set_levels()
        self.reset_rosters()

    def _capture(self):
        players = {row["id"]: row for row in models.Player.objects.values(*PLAYER_FIELDS)}
        stats = {row["id"]: row for row in models.PlayerStatSeason.objects.values(*STAT_FIELDS)}
        return players, stats

    def _career_ids(self, stats):
        return {
            row_id
            for row_id, row in stats.items()
            if row["is_career"] and row["classification"] == "1-mlb"
        }

    def _report(self, before_players, before_stats):
        after_players, after_stats = self._capture()

        level_lines = []
        protect_lines = []
        flag_lines = []
        for player_id, before in before_players.items():
            after = after_players[player_id]
            name = before["name"]
            if before["level"] != after["level"]:
                level_lines.append(f"{name}: {before['level']} -> {after['level']}")
            if before["is_ulmg_protected"] != after["is_ulmg_protected"]:
                before_word = "protected" if before["is_ulmg_protected"] else "unprotected"
                after_word = "protected" if after["is_ulmg_protected"] else "unprotected"
                protect_lines.append(f"{name}: {before_word} -> {after_word}")
            changed = [
                field for field in PLAYER_FLAG_FIELDS if before[field] != after[field]
            ]
            if changed:
                flag_lines.append(f"{name}: {', '.join(changed)}")

        carded_lines = []
        roster_lines = []
        for row_id, before in before_stats.items():
            after = after_stats.get(row_id)
            if after is None:
                continue
            name = before_players[before["player_id"]]["name"]
            if before["carded"] != after["carded"]:
                verb = "set" if after["carded"] else "clear"
                carded_lines.append(
                    f"Would {verb} carded on {name} {before['season']} {before['classification']}."
                )
            changes = [
                f"{field} {before[field]} -> {after[field]}"
                for field in STAT_ROSTER_FIELDS
                if before[field] != after[field]
            ]
            if changes:
                roster_lines.append(f"{name} {before['season']}: {', '.join(changes)}")

        deleted = self._career_ids(before_stats) - set(after_stats)
        written = self._career_ids(after_stats) - set(before_stats)
        still_there = {
            after_stats[row_id]["player_id"] for row_id in self._career_ids(after_stats)
        }
        lost = []
        for row_id in deleted:
            player_id = before_stats[row_id]["player_id"]
            if player_id in still_there:
                continue
            player = before_players.get(player_id)
            if player and player["is_owned"]:
                lost.append(f"{player['name']} would lose a career row.")

        self._write_lines("Level changes:", level_lines)
        self._write_lines("Carded:", carded_lines)
        self.stdout.write(f"Would delete {len(deleted)} career MLB rows.")
        self.stdout.write(f"Would write {len(written)} career MLB rows.")
        self._write_lines("Owned players who would lose a career row:", lost)
        self._write_lines("Protection:", protect_lines)
        self._write_lines("Roster flags:", flag_lines)
        self._write_lines("Season roster rows:", roster_lines)

    def _write_lines(self, header, lines):
        self.stdout.write(header)
        if not lines:
            self.stdout.write("none")
            return
        for line in sorted(lines):
            self.stdout.write(line)

    def handle(self, *args, **options):
        if not options["dry_run"]:
            self._execute()
            return

        self.stdout.write("Dry run. Changes will be rolled back.")
        before_players, before_stats = self._capture()
        with transaction.atomic():
            self._execute()
            self._report(before_players, before_stats)
            transaction.set_rollback(True)
        self.stdout.write("Dry run. No changes saved.")
