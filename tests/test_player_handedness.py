# ABOUTME: Tests for bats/throws from FanGraphs roster resources and UI display.
# ABOUTME: Covers ingest helpers, Player properties, and team/search/detail pages.
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings

from ulmg import models, utils
from ulmg.management.commands.live_update_status_from_fg_rosters import Command


class NormalizeHandTestCase(TestCase):
    def test_normalize_hand_accepts_standard_tokens(self):
        self.assertEqual(utils.normalize_hand("L"), "L")
        self.assertEqual(utils.normalize_hand("r"), "R")
        self.assertEqual(utils.normalize_hand(" S "), "S")

    def test_normalize_hand_rejects_unknown_values(self):
        self.assertIsNone(utils.normalize_hand(""))
        self.assertIsNone(utils.normalize_hand(None))
        self.assertIsNone(utils.normalize_hand("Both"))


class HandsFromFgRosterTestCase(TestCase):
    def test_hands_from_fg_roster_reads_bats_and_throws(self):
        hands = utils.hands_from_fg_roster({"bats": "L", "throws": "R"})
        self.assertEqual(hands, {"bats": "L", "throws": "R"})

    def test_hands_from_fg_roster_uses_handed_for_throws_when_missing(self):
        hands = utils.hands_from_fg_roster({"handed": "L"})
        self.assertEqual(hands, {"bats": None, "throws": "L"})


class PlayerHandednessDisplayTestCase(TestCase):
    def test_bats_throws_display_for_hitters(self):
        p = models.Player.objects.create(
            name="Switch Hitter",
            position="IF",
            level="A",
            bats="S",
            throws="R",
        )
        self.assertEqual(p.bats_throws_display, "S/R")

    def test_throwing_arm_display_for_pitchers(self):
        p = models.Player.objects.create(
            name="Lefty",
            position="P",
            level="A",
            throws="L",
        )
        self.assertEqual(p.throwing_arm_display, "L")
        self.assertIsNone(p.bats_throws_display)


class LiveUpdateStatusFromFgRostersHandednessTestCase(TestCase):
    @patch(
        "ulmg.management.commands.live_update_status_from_fg_rosters.settings.ROSTER_TEAM_IDS",
        [(30, "SFG", "San Francisco Giants")],
    )
    @patch("ulmg.management.commands.live_update_status_from_fg_rosters.utils.s3_manager")
    def test_updates_player_bats_and_throws_from_roster(self, mock_s3):
        roster = [
            {
                "player": "Handed Player",
                "position": "SS",
                "oPlayerId": "55555",
                "mlbamid": 666666,
                "dbTeam": "SFG",
                "role": "1",
                "mlevel": "MLB",
                "type": "mlb-sl",
                "roster40": "Y",
                "bats": "L",
                "throws": "R",
            }
        ]
        mock_s3.get_file_content.return_value = roster

        Command().handle()

        p = models.Player.objects.get()
        self.assertEqual(p.bats, "L")
        self.assertEqual(p.throws, "R")


@override_settings(CURRENT_SEASON=2026)
class PlayerHandednessPageDisplayTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username="mgr", password="secret")
        self.owner = models.Owner.objects.create(user=self.user, name="Manager")
        self.team = models.Team.objects.create(
            city="Test City",
            abbreviation="TST",
            nickname="Testers",
            owner_obj=self.owner,
        )

    def test_team_page_shows_bats_throws_for_hitters_and_arm_for_pitchers(self):
        self.client.login(username="mgr", password="secret")
        hitter = models.Player.objects.create(
            name="Hitter Hands",
            position="IF",
            level="A",
            team=self.team,
            bats="L",
            throws="R",
        )
        pitcher = models.Player.objects.create(
            name="Pitcher Arm",
            position="P",
            level="A",
            team=self.team,
            throws="L",
        )
        for p in (hitter, pitcher):
            models.PlayerStatSeason.objects.create(
                player=p,
                season=2026,
                classification="1-mlb",
                level="MLB",
                is_career=False,
            )

        response = self.client.get("/teams/tst/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "B/T")
        self.assertContains(response, "Arm")
        self.assertContains(response, "L/R")
        self.assertContains(response, ">L<")

    def test_search_page_shows_handedness_columns(self):
        self.client.login(username="mgr", password="secret")
        models.Player.objects.create(
            name="Search Hitter",
            position="IF",
            level="A",
            bats="S",
            throws="R",
        )
        models.Player.objects.create(
            name="Search Pitcher",
            position="P",
            level="A",
            throws="R",
        )

        response = self.client.get("/search/name/?name=Search")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "B/T")
        self.assertContains(response, "Arm")
        self.assertContains(response, "S/R")

    def test_player_detail_shows_handedness(self):
        self.client.login(username="mgr", password="secret")
        p = models.Player.objects.create(
            name="Detail Hitter",
            position="IF",
            level="A",
            bats="L",
            throws="L",
        )

        response = self.client.get(f"/players/{p.id}/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Bats:")
        self.assertContains(response, "Throws:")
        self.assertContains(response, "L/L")
