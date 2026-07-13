# ABOUTME: Tests for second-half (2H) protection UI on team player rows and API actions.
# ABOUTME: Covers V-level slot buttons, 2H-draft exclusions, and roster-tab gating.

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import Client, TestCase, override_settings

from ulmg import models


@override_settings(
    CURRENT_SEASON=2026,
    CURRENT_SEASON_TYPE="midseason",
    TEAM_ROSTER_TAB=True,
    TEAM_PROTECT_TAB=False,
    TEAM_SEASON_HALF="2h",
)
class SecondHalfProtectionUITestCase(TestCase):
    def setUp(self):
        cache.clear()
        self.client = Client()
        self.user = User.objects.create_user(username="mgr", password="secret")
        self.owner = models.Owner.objects.create(user=self.user, name="Manager")
        self.team = models.Team.objects.create(
            city="Test City",
            abbreviation="TST",
            nickname="Testers",
            owner_obj=self.owner,
        )
        self.vet_pitcher = models.Player.objects.create(
            name="Vet Pitcher",
            position="P",
            level="V",
            team=self.team,
            is_owned=True,
        )
        self.vet_catcher = models.Player.objects.create(
            name="Vet Catcher",
            position="C",
            level="V",
            team=self.team,
            is_owned=True,
        )
        self.vet_hitter = models.Player.objects.create(
            name="Vet Hitter",
            position="OF",
            level="V",
            team=self.team,
            is_owned=True,
        )
        self.draft_pick = models.Player.objects.create(
            name="2H Draft Pick",
            position="P",
            level="V",
            team=self.team,
            is_owned=True,
            is_ulmg_2h_draft=True,
        )
        self.a_level = models.Player.objects.create(
            name="A Level Guy",
            position="OF",
            level="A",
            team=self.team,
            is_owned=True,
        )

    def test_owner_sees_2h_protect_buttons_on_player_rows(self):
        self.client.login(username="mgr", password="secret")
        response = self.client.get("/teams/tst/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-action="is_ulmg_2h_p"')
        self.assertContains(response, 'data-action="is_ulmg_2h_c"')
        self.assertContains(response, 'data-action="is_ulmg_2h_pos"')
        self.assertContains(response, 'data-roster-type="2h_p"')
        self.assertContains(response, 'data-roster-type="2h_c"')
        self.assertContains(response, 'data-roster-type="2h_pos"')
        self.assertContains(response, 'id="drop-modal"')
        self.assertContains(response, "Confirm Player Drop")

    def test_owner_sees_active_2h_button_when_already_protected(self):
        self.vet_pitcher.is_ulmg_2h_p = True
        self.vet_pitcher.save()
        cache.clear()
        self.client.login(username="mgr", password="secret")
        response = self.client.get("/teams/tst/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-roster-type="2h_p"')
        self.assertContains(response, 'data-action="unprotect"')
        content = response.content.decode()
        pitcher_idx = content.find("Vet Pitcher")
        self.assertNotEqual(pitcher_idx, -1)
        row_chunk = content[pitcher_idx : pitcher_idx + 2500]
        self.assertIn('data-action="unprotect"', row_chunk)
        self.assertIn('data-roster-type="2h_p"', row_chunk)
        self.assertNotIn('data-action="is_ulmg_2h_p"', row_chunk)

    def test_2h_draft_players_do_not_get_2h_protect_buttons(self):
        self.client.login(username="mgr", password="secret")
        response = self.client.get("/teams/tst/")
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        draft_idx = content.find("2H Draft Pick")
        self.assertNotEqual(draft_idx, -1)
        row_chunk = content[draft_idx : draft_idx + 800]
        self.assertNotIn('data-action="is_ulmg_2h_p"', row_chunk)

    def test_a_level_players_do_not_get_2h_protect_buttons(self):
        self.client.login(username="mgr", password="secret")
        response = self.client.get("/teams/tst/")
        content = response.content.decode()
        a_idx = content.find("A Level Guy")
        self.assertNotEqual(a_idx, -1)
        row_chunk = content[a_idx : a_idx + 800]
        self.assertNotIn('data-action="is_ulmg_2h_pos"', row_chunk)

    def test_non_owner_does_not_see_2h_protect_buttons(self):
        other = User.objects.create_user(username="other", password="secret")
        other_owner = models.Owner.objects.create(user=other, name="Other")
        models.Team.objects.create(
            city="Other City",
            abbreviation="OTH",
            nickname="Others",
            owner_obj=other_owner,
        )
        self.client.login(username="other", password="secret")
        response = self.client.get("/teams/tst/")
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'data-roster-type="2h_p"')
        self.assertNotContains(response, 'id="drop-modal"')

    @override_settings(TEAM_ROSTER_TAB=False)
    def test_protect_buttons_hidden_when_roster_tab_off(self):
        self.client.login(username="mgr", password="secret")
        response = self.client.get("/teams/tst/")
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'data-roster-type="2h_p"')


@override_settings(
    CURRENT_SEASON=2026,
    CURRENT_SEASON_TYPE="midseason",
    TEAM_ROSTER_TAB=True,
    TEAM_SEASON_HALF="2h",
)
class SecondHalfProtectionAPITestCase(TestCase):
    def setUp(self):
        cache.clear()
        self.client = Client()
        self.user = User.objects.create_user(username="mgr", password="secret")
        self.owner = models.Owner.objects.create(user=self.user, name="Manager")
        self.team = models.Team.objects.create(
            city="Test City",
            abbreviation="TST",
            nickname="Testers",
            owner_obj=self.owner,
        )
        self.pitcher = models.Player.objects.create(
            name="API Pitcher",
            position="P",
            level="V",
            team=self.team,
            is_owned=True,
        )
        self.draft_pick = models.Player.objects.create(
            name="API Draft Pick",
            position="P",
            level="V",
            team=self.team,
            is_owned=True,
            is_ulmg_2h_draft=True,
        )
        self.client.login(username="mgr", password="secret")

    def test_api_sets_2h_pitcher_protection(self):
        response = self.client.post(
            f"/api/v1/player/{self.pitcher.id}/is_ulmg_2h_p/"
        )
        self.assertEqual(response.status_code, 200)
        self.pitcher.refresh_from_db()
        self.assertTrue(self.pitcher.is_ulmg_2h_p)
        self.assertTrue(self.pitcher.is_ulmg_protected)

    def test_api_rejects_2h_protection_for_2h_draft_pick(self):
        response = self.client.post(
            f"/api/v1/player/{self.draft_pick.id}/is_ulmg_2h_p/"
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"error", response.content)
        self.draft_pick.refresh_from_db()
        self.assertFalse(self.draft_pick.is_ulmg_2h_p)

    def test_api_2h_slot_is_exclusive_per_team(self):
        other = models.Player.objects.create(
            name="Other Pitcher",
            position="P",
            level="V",
            team=self.team,
            is_owned=True,
            is_ulmg_2h_p=True,
        )
        response = self.client.post(
            f"/api/v1/player/{self.pitcher.id}/is_ulmg_2h_p/"
        )
        self.assertEqual(response.status_code, 200)
        other.refresh_from_db()
        self.pitcher.refresh_from_db()
        self.assertFalse(other.is_ulmg_2h_p)
        self.assertTrue(self.pitcher.is_ulmg_2h_p)
