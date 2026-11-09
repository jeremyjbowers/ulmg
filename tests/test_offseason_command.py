# ABOUTME: Tests the offseason command's --dry-run report and the live run it previews.
# ABOUTME: A dry run must show level, carded, career, and roster changes and then leave the database as it found it.

import csv
import tempfile
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase, override_settings

from ulmg import models


HIT_FIELDS = ["playerid", "mlbamid", "PA", "G"]
PITCH_FIELDS = ["playerid", "mlbamid", "GS", "G", "IP"]


def write_csv(path, fields, rows):
    with open(path, "w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def snapshot():
    players = list(
        models.Player.objects.order_by("id").values(
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
        )
    )
    stats = list(
        models.PlayerStatSeason.objects.order_by("id").values(
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
        )
    )
    return players, stats


@override_settings(CURRENT_SEASON=2026, CURRENT_SEASON_TYPE="offseason")
class OffseasonDryRunTests(TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.team = models.Team.objects.create(
            city="Test City", abbreviation="TST", nickname="Testers"
        )
        root = Path(self.tmp.name)
        self.hit_csv = root / "hit.csv"
        self.pitch_csv = root / "pitch.csv"
        write_csv(
            self.hit_csv,
            HIT_FIELDS,
            [
                {"playerid": "9001", "mlbamid": "", "PA": "3000", "G": "400"},
                {"playerid": "9004", "mlbamid": "", "PA": "100", "G": "40"},
                {"playerid": "9006", "mlbamid": "", "PA": "3000", "G": "400"},
            ],
        )
        write_csv(
            self.pitch_csv,
            PITCH_FIELDS,
            [{"playerid": "9002", "mlbamid": "", "GS": "5", "G": "40", "IP": "40"}],
        )
        self.casey = self.player("Casey Prospect", "OF", "B", "9001", owned=True)
        self.reliever = self.player(
            "Reliever Rookie",
            "P",
            "B",
            "9002",
            owned=True,
            team=self.team,
            is_ulmg_1h_p=True,
            is_ulmg_mlb_roster=True,
        )
        self.ace = self.player("Uncarded Ace", "P", "A", "9003", owned=True)
        self.short = self.player(
            "Short Season", "OF", "B", "9004", owned=True, is_ulmg_2h_draft=True
        )
        self.vet = self.player(
            "Old Vet", "OF", "V", "9005", owned=True, is_ulmg_protected=True
        )
        self.free = self.player("Free Agent Prospect", "OF", "B", "9006", owned=False)
        self.stale = self.player(
            "Stale Star", "OF", "B", "9007", owned=True, is_ulmg_protected=True
        )
        self.ghost = self.player("Unowned Ghost", "OF", "B", "9008", owned=False)

        self.season_row(
            self.casey, hit_stats={"pa": 100, "g": 40}, roster_status="Active", mlb_org="NYY"
        )
        models.PlayerStatSeason.objects.filter(player=self.casey, is_career=False).update(
            carded=False, is_ulmg_mlb_roster=True
        )
        self.season_row(self.reliever, pitch_stats={"ip": 10, "g": 10})
        self.season_row(self.ace)
        models.PlayerStatSeason.objects.filter(player=self.ace, is_career=False).update(carded=True)
        self.season_row(self.short, hit_stats={"pa": 50, "g": 20})
        self.season_row(self.vet, hit_stats={"pa": 200, "g": 80})
        self.season_row(self.free, hit_stats={"pa": 20, "g": 10})
        self.season_row(self.stale, hit_stats={"pa": 10, "g": 5})
        self.career_row(self.casey, hit_stats={"pa": 10, "g": 5})
        self.career_row(self.stale, hit_stats={"pa": 5000, "g": 900})
        self.career_row(self.ghost, hit_stats={"pa": 4000, "g": 700})

    def tearDown(self):
        self.tmp.cleanup()

    def player(self, name, position, level, fg_id, owned, **flags):
        # Player.save() clears is_owned when there is no team.
        if owned and "team" not in flags:
            flags["team"] = self.team
        return models.Player.objects.create(
            name=name,
            position=position,
            level=level,
            fg_id=fg_id,
            is_owned=owned,
            **flags,
        )

    def season_row(self, player, hit_stats=None, pitch_stats=None, roster_status=None, mlb_org=None):
        return models.PlayerStatSeason.objects.create(
            player=player,
            season=2025,
            classification="1-mlb",
            is_career=False,
            hit_stats=hit_stats,
            pitch_stats=pitch_stats,
            roster_status=roster_status,
            mlb_org=mlb_org,
        )

    def career_row(self, player, hit_stats):
        return models.PlayerStatSeason.objects.create(
            player=player,
            season=None,
            classification="1-mlb",
            is_career=True,
            hit_stats=hit_stats,
        )

    def command(self, *args):
        out = StringIO()
        with patch("ulmg.management.commands.offseason.HIT_CSV", str(self.hit_csv)), patch(
            "ulmg.management.commands.offseason.PITCH_CSV", str(self.pitch_csv)
        ):
            call_command("offseason", *args, stdout=out)
        return out.getvalue()

    def test_dry_run_reports_changes_and_writes_nothing(self):
        before = snapshot()
        output = self.command("--dry-run")
        self.assertEqual(snapshot(), before)

        self.assertIn("Dry run. No changes saved.", output)
        self.assertIn("Casey Prospect: B -> V", output)
        self.assertIn("Free Agent Prospect: B -> V", output)
        self.assertIn("Reliever Rookie: B -> A", output)
        self.assertNotIn("Short Season: B ->", output)
        self.assertNotIn("Stale Star: B ->", output)
        self.assertNotIn("Old Vet: V ->", output)

        self.assertIn("Would set carded on Casey Prospect 2025 1-mlb.", output)
        self.assertIn("Would clear carded on Uncarded Ace 2025 1-mlb.", output)
        self.assertIn("Would delete 3 career MLB rows.", output)
        self.assertIn("Would write 4 career MLB rows.", output)
        self.assertIn("Stale Star would lose a career row.", output)
        self.assertNotIn("Unowned Ghost would lose a career row.", output)

        self.assertIn("Uncarded Ace: unprotected -> protected", output)
        self.assertIn("Old Vet: protected -> unprotected", output)
        self.assertIn("Reliever Rookie: is_ulmg_1h_p, is_ulmg_mlb_roster", output)
        self.assertIn("Short Season: is_ulmg_2h_draft", output)
        self.assertIn("Casey Prospect 2025: roster_status Active -> None", output)
        self.assertIn("mlb_org NYY -> None", output)
        self.assertIn("is_ulmg_mlb_roster True -> False", output)

    def test_live_run_applies_the_same_changes(self):
        self.command()

        self.casey.refresh_from_db()
        self.free.refresh_from_db()
        self.reliever.refresh_from_db()
        self.ace.refresh_from_db()
        self.short.refresh_from_db()
        self.vet.refresh_from_db()
        self.stale.refresh_from_db()

        self.assertEqual(self.casey.level, "V")
        self.assertEqual(self.free.level, "V")
        self.assertEqual(self.reliever.level, "A")
        self.assertEqual(self.short.level, "B")
        self.assertEqual(self.stale.level, "B")
        self.assertTrue(self.stale.is_ulmg_protected)
        self.assertFalse(self.reliever.is_ulmg_1h_p)
        self.assertFalse(self.reliever.is_ulmg_mlb_roster)
        self.assertFalse(self.short.is_ulmg_2h_draft)
        self.assertTrue(self.ace.is_ulmg_protected)
        self.assertFalse(self.vet.is_ulmg_protected)

        casey_season = models.PlayerStatSeason.objects.get(player=self.casey, is_career=False)
        self.assertTrue(casey_season.carded)
        self.assertIsNone(casey_season.roster_status)
        self.assertIsNone(casey_season.mlb_org)
        self.assertFalse(casey_season.is_ulmg_mlb_roster)
        ace_season = models.PlayerStatSeason.objects.get(player=self.ace, is_career=False)
        self.assertFalse(ace_season.carded)

        casey_career = models.PlayerStatSeason.objects.get(player=self.casey, is_career=True)
        self.assertEqual(casey_career.hit_stats["pa"], 3000)
        self.assertFalse(
            models.PlayerStatSeason.objects.filter(player=self.stale, is_career=True).exists()
        )
        self.assertFalse(
            models.PlayerStatSeason.objects.filter(player=self.ghost, is_career=True).exists()
        )
        self.assertEqual(
            models.PlayerStatSeason.objects.filter(is_career=True, classification="1-mlb").count(),
            4,
        )
