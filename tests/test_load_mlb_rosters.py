# ABOUTME: Tests for load_mlb_rosters command.
# ABOUTME: Ensures roster fetch and all_mlb_rosters.json output work correctly.
import json
import tempfile
from unittest.mock import patch, MagicMock

from django.test import TestCase

from ulmg.management.commands.load_mlb_rosters import Command


class LoadMlbRostersTestCase(TestCase):
    """Test load_mlb_rosters command."""

    def setUp(self):
        self.cmd = Command()

    def test_get_mlb_org_uses_abbreviation_for_mlb_teams(self):
        team = {"sport": {"id": 1}, "abbreviation": "SF"}
        self.assertEqual(self.cmd._get_mlb_org(team), "SF")

    def test_get_mlb_org_uses_parent_lookup_for_minors(self):
        team = {"sport": {"id": 16}, "parentOrgId": 137}
        self.assertEqual(self.cmd._get_mlb_org(team), "SF")

    def test_roster_status_active_mlb_returns_mlb(self):
        team = {"sport": {"id": 1}}
        self.assertEqual(self.cmd._roster_status(team, "Active"), "MLB")

    def test_roster_status_minors_returns_minors(self):
        team = {"sport": {"id": 16}}
        self.assertEqual(self.cmd._roster_status(team, "Active"), "MINORS")

    def test_roster_status_injured_60_returns_il60(self):
        team = {"sport": {"id": 1}}
        self.assertEqual(self.cmd._roster_status(team, "Injured 60-Day"), "IL-60")

    @patch("ulmg.management.commands.load_mlb_rosters.requests.get")
    def test_handle_writes_all_mlb_rosters_json(self, mock_get):
        mock_get.return_value.json.side_effect = [
            {
                "teams": [
                    {
                        "id": 137,
                        "name": "San Francisco Giants",
                        "sport": {"id": 1},
                        "abbreviation": "SF",
                        "parentOrgId": None,
                    },
                    {
                        "id": 2101,
                        "name": "DSL Brewers Gold",
                        "sport": {"id": 16},
                        "abbreviation": "D-BWG",
                        "parentOrgId": 158,
                    },
                ]
            },
            {
                "roster": [
                    {
                        "person": {"id": 12345, "fullName": "Test MLB Player"},
                        "position": {"abbreviation": "SS"},
                        "status": {"description": "Active"},
                    }
                ]
            },
            {
                "roster": [
                    {
                        "person": {"id": 67890, "fullName": "Test DSL Player"},
                        "position": {"abbreviation": "P"},
                        "status": {"description": "Active"},
                    }
                ]
            },
        ]
        mock_get.return_value.raise_for_status = MagicMock()

        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = f"{tmpdir}/rosters/all_mlb_rosters.json"
            with patch(
                "ulmg.management.commands.load_mlb_rosters.settings.CURRENT_SEASON", 2025
            ):
                with patch(
                    "ulmg.management.commands.load_mlb_rosters.os.path.dirname",
                    return_value=f"{tmpdir}/rosters",
                ):
                    with patch(
                        "ulmg.management.commands.load_mlb_rosters.open",
                        create=True,
                    ) as mock_open:
                        mock_file = MagicMock()
                        mock_open.return_value.__enter__.return_value = mock_file
                        with patch(
                            "ulmg.management.commands.load_mlb_rosters.os.makedirs"
                        ):
                            self.cmd.handle()

        written = mock_file.write.call_args[0][0]
        players = json.loads(written)
        self.assertEqual(len(players), 2)
        by_id = {p["mlbam_id"]: p for p in players}
        self.assertIn(12345, by_id)
        self.assertEqual(by_id[12345]["name"], "Test MLB Player")
        self.assertEqual(by_id[12345]["mlb_org"], "SF")
        self.assertEqual(by_id[12345]["roster_status"], "MLB")
        self.assertIn(67890, by_id)
        self.assertEqual(by_id[67890]["mlb_org"], "MIL")
        self.assertEqual(by_id[67890]["roster_status"], "MINORS")
