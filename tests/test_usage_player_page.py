# ABOUTME: End-to-end tests for remaining ULMG usage shown on the player page.
# ABOUTME: Requests the real page through the test client and checks it reads the live counters.

from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from ulmg import models, usage
from tests.usage_fixtures import (
    ULMG_SEASON,
    create_hitter,
    create_pitcher,
    create_series,
    create_teams,
)


@override_settings(CURRENT_SEASON=ULMG_SEASON)
class PlayerPageUsageTestCase(TestCase):
    def setUp(self):
        self.client.force_login(User.objects.create_user("manager"))
        home, road = create_teams()
        self.game = create_series(home, road, length=3)[0]
        self.hitter = create_hitter("Platoon Bat", ab=200, pa=220, k_pct=0.2, bb_pct=0.1)
        self.pitcher = create_pitcher("Setup Man", ip=65, g=65, gs=0, relief_minusip=65)

    def test_batter_page_shows_live_remaining_plate_appearances(self):
        response = self.client.get(f"/players/{self.hitter.id}/")
        self.assertContains(response, f"{ULMG_SEASON} ULMG usage")
        self.assertContains(response, "220 of 220 plate appearances left")

        usage.record_plate_appearance(self.game, self.hitter, self.pitcher, at_bat=False, outs=0)
        response = self.client.get(f"/players/{self.hitter.id}/")
        self.assertContains(response, "219 of 220 plate appearances left")

    def test_unlimited_batter(self):
        regular = create_hitter("Regular", ab=600, pa=650, k_pct=0.2, bb_pct=0.1)
        response = self.client.get(f"/players/{regular.id}/")
        self.assertContains(response, "Unlimited plate appearances")

    def test_pitcher_page_shows_innings_and_per_game_limits(self):
        usage.record_plate_appearance(self.game, self.hitter, self.pitcher, at_bat=True, outs=1)
        response = self.client.get(f"/players/{self.pitcher.id}/")
        # 65 innings at 125% is 243 outs; one used.
        self.assertContains(response, "80.2 of 81.0 innings left")
        self.assertContains(response, "0 of 0 starts left")
        self.assertContains(response, "Per game: 4.0 innings in a start, 2.0 in relief")

    def test_usage_is_shown_in_the_card_block_when_the_player_has_a_card(self):
        models.Card.objects.create(player=self.hitter, season=ULMG_SEASON - 1)
        content = self.client.get(f"/players/{self.hitter.id}/").content.decode()
        card_heading = content.index(f"{ULMG_SEASON - 1} Card")
        usage_line = content.index("220 of 220 plate appearances left")
        transactions = content.find("Transaction History")
        self.assertLess(card_heading, usage_line)
        self.assertEqual(content.count(f"{ULMG_SEASON} ULMG usage"), 1)
        if transactions != -1:
            self.assertLess(usage_line, transactions)

    def test_viewing_a_player_does_not_create_a_counter(self):
        self.client.get(f"/players/{self.hitter.id}/")
        self.assertFalse(models.UsageCounter.objects.exists())
