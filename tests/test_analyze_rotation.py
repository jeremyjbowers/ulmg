# ABOUTME: Tests for the analyze_rotation management command.
# ABOUTME: Verifies pitching IP and GS totals by xFIP/SIERA threshold buckets.
import io
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase, override_settings

from ulmg import models


class AnalyzeRotationTestCase(TestCase):
    def setUp(self):
        self.team = models.Team.objects.create(
            city="Testville",
            abbreviation="TST",
            nickname="Testers",
        )
        self.other_team = models.Team.objects.create(
            city="Otherburg",
            abbreviation="OTH",
            nickname="Others",
        )

    def _create_pitcher(self, team, name, pitch_stats, **stat_season_kwargs):
        player = models.Player.objects.create(
            name=name,
            team=team,
            position=stat_season_kwargs.pop("position", "P"),
            level="A",
        )
        models.PlayerStatSeason.objects.create(
            player=player,
            season=2025,
            classification="1-mlb",
            pitch_stats=pitch_stats,
            **stat_season_kwargs,
        )

    @override_settings(CURRENT_SEASON=2026, CURRENT_SEASON_TYPE="offseason")
    @patch("sys.stdout", new_callable=io.StringIO)
    def test_sums_ip_and_gs_by_xfip_threshold(self, mock_stdout):
        self._create_pitcher(
            self.team,
            "Ace Pitcher",
            {"ip": 100, "gs": 20, "xfip": 2.8, "siera": 2.9},
        )
        self._create_pitcher(
            self.team,
            "Good Pitcher",
            {"ip": 80, "gs": 15, "xfip": 3.2, "siera": 3.3},
        )
        self._create_pitcher(
            self.team,
            "Average Pitcher",
            {"ip": 60, "gs": 10, "xfip": 3.8, "siera": 3.9},
        )
        self._create_pitcher(
            self.team,
            "Below Minimum IP",
            {"ip": 2, "gs": 1, "xfip": 2.5, "siera": 2.5},
        )
        self._create_pitcher(
            self.other_team,
            "Other Ace",
            {"ip": 50, "gs": 8, "xfip": 2.9, "siera": 3.0},
        )

        call_command("analyze_rotation", metric="xfip")

        output = mock_stdout.getvalue()
        lines = [line for line in output.strip().splitlines() if line]

        self.assertEqual(lines[0], "innings_pitched,team,<3,<3.5,<4")
        self.assertIn("TST,100,180,240", lines)
        self.assertIn("OTH,50,50,50", lines)

        gs_header_index = next(i for i, line in enumerate(lines) if line.startswith("starts,"))
        self.assertEqual(lines[gs_header_index], "starts,team,<3,<3.5,<4")
        self.assertIn("TST,20,35,45", lines)
        self.assertIn("OTH,8,8,8", lines)

    @override_settings(CURRENT_SEASON=2026, CURRENT_SEASON_TYPE="offseason")
    @patch("sys.stdout", new_callable=io.StringIO)
    def test_uses_siera_when_requested(self, mock_stdout):
        self._create_pitcher(
            self.team,
            "SIERA Only Good",
            {"ip": 90, "gs": 18, "xfip": 4.5, "siera": 3.1},
        )

        call_command("analyze_rotation", metric="siera")

        output = mock_stdout.getvalue()
        ip_line = next(line for line in output.splitlines() if line.startswith("TST,"))
        self.assertEqual(ip_line, "TST,0,90,90")

    @override_settings(CURRENT_SEASON=2026, CURRENT_SEASON_TYPE="offseason")
    @patch("sys.stdout", new_callable=io.StringIO)
    def test_excludes_milb_and_non_pitchers(self, mock_stdout):
        self._create_pitcher(
            self.team,
            "MLB Ace",
            {"ip": 100, "gs": 20, "xfip": 2.8},
        )
        self._create_pitcher(
            self.team,
            "Second MLB Ace",
            {"ip": 100, "gs": 20, "xfip": 2.8},
        )
        milb_pitcher = models.Player.objects.create(
            name="MiLB Only",
            team=self.team,
            position="P",
            level="B",
        )
        models.PlayerStatSeason.objects.create(
            player=milb_pitcher,
            season=2025,
            classification="2-milb",
            pitch_stats={"ip": 120, "gs": 25, "xfip": 2.5},
        )
        self._create_pitcher(
            self.team,
            "MLB Hitter",
            {"ip": 100, "gs": 20, "xfip": 2.8},
            position="IF",
        )

        call_command("analyze_rotation", metric="xfip")

        output = mock_stdout.getvalue()
        ip_line = next(line for line in output.splitlines() if line.startswith("TST,"))
        self.assertEqual(ip_line, "TST,200,200,200")
