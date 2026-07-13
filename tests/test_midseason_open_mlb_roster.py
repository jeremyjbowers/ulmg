# ABOUTME: Tests that midseason Open draft picks land on the MLB roster.
# ABOUTME: Covers live draft_action and the post-draft midseason management command.

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import Client, TestCase, override_settings
from io import StringIO

from ulmg import models


@override_settings(CURRENT_SEASON=2026, CURRENT_SEASON_TYPE="midseason")
class MidseasonOpenDraftMlbRosterTestCase(TestCase):
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
        self.player = models.Player.objects.create(
            name="Open Pick",
            position="OF",
            level="V",
            is_owned=False,
        )
        self.pick = models.DraftPick.objects.create(
            year="2026",
            season="midseason",
            draft_type="open",
            draft_round=1,
            pick_number=1,
            team=self.team,
        )
        self.client.login(username="mgr", password="secret")

    def test_draft_action_puts_midseason_open_pick_on_mlb_roster(self):
        response = self.client.get(
            f"/api/v1/draft/{self.pick.id}/",
            {"playerid": self.player.id},
        )
        self.assertEqual(response.status_code, 200)
        self.player.refresh_from_db()
        self.pick.refresh_from_db()
        self.assertEqual(self.pick.player_id, self.player.id)
        self.assertEqual(self.player.team_id, self.team.id)
        self.assertTrue(self.player.is_ulmg_mlb_roster)
        self.assertTrue(self.player.is_ulmg_2h_draft)
        self.assertTrue(self.player.is_owned)

    def test_draft_action_name_format_also_sets_mlb_and_2h_draft(self):
        response = self.client.get(
            f"/api/v1/draft/{self.pick.id}/",
            {"name": f"OF Open Pick [NYY] [123] | {self.player.id}"},
        )
        self.assertEqual(response.status_code, 200)
        self.player.refresh_from_db()
        self.assertTrue(self.player.is_ulmg_mlb_roster)
        self.assertTrue(self.player.is_ulmg_2h_draft)
        self.assertEqual(self.player.team_id, self.team.id)

    def test_draft_action_mirrors_mlb_roster_to_playerstatseason(self):
        response = self.client.get(
            f"/api/v1/draft/{self.pick.id}/",
            {"playerid": self.player.id},
        )
        self.assertEqual(response.status_code, 200)
        pss = models.PlayerStatSeason.objects.get(player=self.player, season=2026)
        self.assertTrue(pss.is_ulmg_mlb_roster)
        self.assertFalse(pss.is_ulmg_aaa_roster)

    def test_draft_action_does_not_force_mlb_for_aa_draft(self):
        aa_pick = models.DraftPick.objects.create(
            year="2026",
            season="midseason",
            draft_type="aa",
            draft_round=1,
            pick_number=1,
            team=self.team,
        )
        prospect = models.Player.objects.create(
            name="AA Prospect",
            position="P",
            level="B",
            is_owned=False,
        )
        response = self.client.get(
            f"/api/v1/draft/{aa_pick.id}/",
            {"playerid": prospect.id},
        )
        self.assertEqual(response.status_code, 200)
        prospect.refresh_from_db()
        self.assertFalse(prospect.is_ulmg_mlb_roster)
        self.assertFalse(prospect.is_ulmg_2h_draft)

    def test_undo_draft_pick_clears_mlb_and_2h_draft(self):
        self.player.team = self.team
        self.player.is_ulmg_mlb_roster = True
        self.player.is_ulmg_2h_draft = True
        self.player.save()
        self.pick.player = self.player
        self.pick.save()

        response = self.client.get(f"/api/v1/draft/{self.pick.id}/")
        self.assertEqual(response.status_code, 200)
        self.player.refresh_from_db()
        self.pick.refresh_from_db()
        self.assertIsNone(self.pick.player)
        self.assertIsNone(self.player.team)
        self.assertFalse(self.player.is_ulmg_mlb_roster)
        self.assertFalse(self.player.is_ulmg_2h_draft)


@override_settings(CURRENT_SEASON=2026, CURRENT_SEASON_TYPE="midseason")
class MidseasonCommandMlbRosterTestCase(TestCase):
    def setUp(self):
        self.team = models.Team.objects.create(
            city="Test City",
            abbreviation="TST",
            nickname="Testers",
        )
        self.drafted = models.Player.objects.create(
            name="Drafted Vet",
            position="OF",
            level="V",
            team=self.team,
            is_owned=True,
        )
        self.one_h = models.Player.objects.create(
            name="1H Protected",
            position="P",
            level="V",
            team=self.team,
            is_owned=True,
            is_ulmg_1h_p=True,
        )
        self.other_mlb = models.Player.objects.create(
            name="Other MLB",
            position="C",
            level="V",
            team=self.team,
            is_owned=True,
            is_ulmg_mlb_roster=True,
        )
        models.DraftPick.objects.create(
            year="2026",
            season="midseason",
            draft_type="open",
            draft_round=1,
            pick_number=1,
            team=self.team,
            player=self.drafted,
        )

    def test_midseason_command_marks_open_picks_mlb_and_2h_draft(self):
        out = StringIO()
        call_command("midseason", stdout=out)
        self.drafted.refresh_from_db()
        self.one_h.refresh_from_db()
        self.other_mlb.refresh_from_db()

        self.assertTrue(self.drafted.is_ulmg_mlb_roster)
        self.assertTrue(self.drafted.is_ulmg_2h_draft)
        self.assertTrue(self.one_h.is_ulmg_mlb_roster)
        self.assertFalse(self.other_mlb.is_ulmg_mlb_roster)

    def test_midseason_command_dry_run_makes_no_changes(self):
        out = StringIO()
        call_command("midseason", "--dry-run", stdout=out)
        self.drafted.refresh_from_db()
        self.other_mlb.refresh_from_db()
        self.assertFalse(self.drafted.is_ulmg_2h_draft)
        self.assertTrue(self.other_mlb.is_ulmg_mlb_roster)
        self.assertIn("Would", out.getvalue())
