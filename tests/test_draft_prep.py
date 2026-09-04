# ABOUTME: Tests for offseason and midseason draft-prep eligibility and team-page links.
# ABOUTME: Covers AA (B-only) vs Open (V/A ranking board; midseason Open still requires a prior-year card).

from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings

from ulmg import models, utils


def _wishlist_player(wishlist, name, level, position="OF", team=None, carded_seasons=None):
    player = models.Player.objects.create(
        name=name,
        position=position,
        level=level,
        team=team,
        carded_seasons=carded_seasons or [],
    )
    models.WishlistPlayer.objects.create(wishlist=wishlist, player=player, rank=1)
    return player


@override_settings(CURRENT_SEASON=2026, CURRENT_SEASON_TYPE="midseason")
class DraftPrepEligibilityUnitTestCase(TestCase):
    def test_aa_filters_are_unowned_b_only(self):
        self.assertEqual(
            utils.get_draft_prep_player_filters("aa", list_type="offseason"),
            {"team__isnull": True, "level": "B"},
        )
        self.assertEqual(
            utils.get_draft_prep_player_filters("aa", list_type="midseason"),
            {"team__isnull": True, "level": "B"},
        )

    def test_offseason_open_filters_are_unowned_v_and_a(self):
        self.assertEqual(
            utils.get_draft_prep_player_filters("open", list_type="offseason"),
            {"team__isnull": True, "level__in": ["V", "A"]},
        )

    def test_midseason_open_filters_require_prior_year_card(self):
        self.assertEqual(
            utils.get_draft_prep_player_filters("open", list_type="midseason"),
            {"team__isnull": True, "carded_seasons__contains": [2025]},
        )

    def test_aa_offseason_prep_year_bumps_during_midseason(self):
        self.assertEqual(
            utils.get_draft_prep_year_season("aa", list_type="offseason"),
            (2027, "offseason"),
        )


@override_settings(
    CURRENT_SEASON=2026,
    CURRENT_SEASON_TYPE="midseason",
    DRAFT_PREP_SEASON_TYPE="offseason",
)
class DraftPrepViewIntegrationTestCase(TestCase):
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
        self.wishlist = models.Wishlist.objects.create(owner=self.owner)
        self.unowned_v = _wishlist_player(self.wishlist, "Unowned Veteran", "V")
        self.unowned_a = _wishlist_player(self.wishlist, "Unowned A-Level", "A")
        self.uncarded_b = _wishlist_player(self.wishlist, "Uncarded B Prospect", "B")
        self.carded_b = _wishlist_player(
            self.wishlist, "Carded B Prospect", "B", carded_seasons=[2025]
        )
        self.owned_b = _wishlist_player(
            self.wishlist, "Owned B Prospect", "B", team=self.team
        )
        self.client.login(username="mgr", password="secret")

    def test_offseason_open_includes_unowned_v_and_a_without_card(self):
        response = self.client.get("/my/offseason/draft/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Unowned Veteran")
        self.assertContains(response, "Unowned A-Level")
        self.assertNotContains(response, "Uncarded B Prospect")
        self.assertNotContains(response, "Carded B Prospect")
        self.assertNotContains(response, "Owned B Prospect")
        self.assertEqual(response.context["draft_season"], "offseason")
        self.assertEqual(response.context["draft_type"], "open")

    def test_midseason_open_requires_prior_year_card_and_allows_b(self):
        response = self.client.get("/my/midseason/draft/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Carded B Prospect")
        self.assertNotContains(response, "Uncarded B Prospect")
        self.assertNotContains(response, "Unowned Veteran")
        self.assertNotContains(response, "Unowned A-Level")
        self.assertEqual(response.context["draft_season"], "midseason")

    def test_offseason_aa_is_unowned_b_only(self):
        response = self.client.get("/my/wishlist/draft/beta/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Uncarded B Prospect")
        self.assertContains(response, "Carded B Prospect")
        self.assertNotContains(response, "Unowned Veteran")
        self.assertNotContains(response, "Unowned A-Level")
        self.assertNotContains(response, "Owned B Prospect")
        self.assertEqual(response.context["draft_type"], "aa")
        self.assertEqual(response.context["draft_season"], "offseason")


@override_settings(
    CURRENT_SEASON=2026,
    CURRENT_SEASON_TYPE="midseason",
    DRAFT_PREP_SEASON_TYPE="offseason",
)
class DraftPrepTeamPageE2ETestCase(TestCase):
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
        self.wishlist = models.Wishlist.objects.create(owner=self.owner)
        self.uncarded_b = _wishlist_player(self.wishlist, "Offseason Eligible B", "B")
        self.unowned_v = _wishlist_player(self.wishlist, "Offseason Eligible V", "V")
        self.client.login(username="mgr", password="secret")

    def test_team_page_draft_links_go_to_offseason_prep(self):
        team_page = self.client.get("/teams/tst/")
        self.assertEqual(team_page.status_code, 200)
        self.assertContains(team_page, 'href="/my/offseason/draft/"')
        self.assertContains(team_page, 'href="/my/wishlist/draft/beta/"')
        self.assertNotContains(team_page, 'href="/my/midseason/draft/"')

        trades_page = self.client.get("/teams/tst/other/")
        self.assertEqual(trades_page.status_code, 200)
        self.assertContains(trades_page, 'href="/my/offseason/draft/"')
        self.assertContains(trades_page, 'href="/my/wishlist/draft/beta/"')

        open_prep = self.client.get("/my/offseason/draft/")
        self.assertEqual(open_prep.status_code, 200)
        self.assertNotContains(open_prep, "Offseason Eligible B")
        self.assertContains(open_prep, "Offseason Eligible V")

        aa_prep = self.client.get("/my/wishlist/draft/beta/")
        self.assertEqual(aa_prep.status_code, 200)
        self.assertContains(aa_prep, "Offseason Eligible B")
        self.assertNotContains(aa_prep, "Offseason Eligible V")
