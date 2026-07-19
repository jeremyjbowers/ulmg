# ABOUTME: Tests for scrape_mlb_data birthdate and metadata backfill from MLB API.
# ABOUTME: Ensures archive command uses current_mlb_org instead of removed Player.mlb_org.
import datetime
from io import StringIO
from unittest.mock import MagicMock, patch

from django.conf import settings
from django.test import TestCase

from ulmg import models
from ulmg.management.commands.archive_mlb_scrape_data import Command


class ArchiveMlbScrapeDataTestCase(TestCase):
    @patch("ulmg.management.commands.archive_mlb_scrape_data.time.sleep")
    @patch("ulmg.management.commands.archive_mlb_scrape_data.requests.get")
    def test_backfills_birthdate_position_and_current_mlb_org(self, mock_get, _mock_sleep):
        player = models.Player.objects.create(
            name="Test Scrape Player",
            mlbam_id="123456",
            position="DH",
        )
        mock_get.return_value = MagicMock(
            json=lambda: {
                "people": [
                    {
                        "birthDate": "1994-06-09",
                        "primaryPosition": {"abbreviation": "SS"},
                        "currentTeam": {
                            "abbreviation": "BOS",
                            "sport": {"id": 1},
                        },
                    }
                ]
            }
        )

        out = StringIO()
        Command(stdout=out).handle()

        player.refresh_from_db()
        self.assertEqual(player.birthdate, datetime.date(1994, 6, 9))
        self.assertEqual(player.position, "IF")
        self.assertEqual(player.current_mlb_org, "BOS")
        pss = models.PlayerStatSeason.objects.get(
            player=player,
            season=settings.CURRENT_SEASON,
            is_career=False,
        )
        self.assertEqual(pss.mlb_org, "BOS")
        output = out.getvalue()
        self.assertIn("Test Scrape Player", output)
        self.assertIn("UPDATED", output)
        self.assertIn("birthdate -> 1994-06-09", output)
        self.assertIn("position DH -> IF", output)
        self.assertIn("current_mlb_org none -> BOS", output)

    @patch("ulmg.management.commands.archive_mlb_scrape_data.time.sleep")
    @patch("ulmg.management.commands.archive_mlb_scrape_data.requests.get")
    def test_updates_mlb_org_when_player_was_traded(self, mock_get, _mock_sleep):
        player = models.Player.objects.create(
            name="Traded Player",
            mlbam_id="999999",
            position="IF",
            birthdate=datetime.date(1995, 1, 1),
            current_mlb_org="NYY",
        )
        models.PlayerStatSeason.objects.create(
            player=player,
            season=settings.CURRENT_SEASON,
            classification="1-mlb",
            mlb_org="NYY",
            owned=False,
            carded=False,
        )
        mock_get.return_value = MagicMock(
            json=lambda: {
                "people": [
                    {
                        "birthDate": "1995-01-01",
                        "primaryPosition": {"abbreviation": "SS"},
                        "currentTeam": {
                            "abbreviation": "BOS",
                            "sport": {"id": 1},
                        },
                    }
                ]
            }
        )

        Command().handle(all=True)

        player.refresh_from_db()
        self.assertEqual(player.current_mlb_org, "BOS")
        pss = models.PlayerStatSeason.objects.get(
            player=player,
            season=settings.CURRENT_SEASON,
            is_career=False,
        )
        self.assertEqual(pss.mlb_org, "BOS")

    def test_milb_current_team_uses_parent_org_id(self):
        cmd = Command()
        org = cmd._mlb_org_from_current_team(
            {
                "abbreviation": "WOR",
                "sport": {"id": 11},
                "parentOrgId": 111,
                "parentOrgName": "Boston Red Sox",
            }
        )
        self.assertEqual(org, "BOS")
