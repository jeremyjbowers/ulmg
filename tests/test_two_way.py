# ABOUTME: A two-way player hits and pitches. A pitcher with a short batting line stays a pitcher.
# ABOUTME: Covers position codes, the card promotion, and the player page showing both stat tables.

from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings

from ulmg import cards, models, utils


def logged_in_client():
    User.objects.create_user("mgr", "mgr@example.com", "password")
    client = Client()
    client.login(username="mgr", password="password")
    return client


class NormalizeTwoWayTestCase(TestCase):
    def test_a_hitter_who_pitches_keeps_both_sides(self):
        for raw in ("DH/SP", "SP/DH", "DH-P", "TWP", "dh/sp"):
            self.assertEqual(utils.normalize_pos(raw), "DH-P")
        self.assertEqual(utils.normalize_pos("OF-P"), "OF-P")
        self.assertEqual(utils.normalize_pos("LF/SP"), "OF-P")
        self.assertEqual(utils.normalize_pos("IF-P"), "IF-P")
        self.assertEqual(utils.normalize_pos("SS/P"), "IF-P")
        self.assertEqual(utils.normalize_pos("C/P"), "IF-P")

    def test_a_pitcher_stays_a_pitcher(self):
        for raw in ("P", "SP", "RP", "Pitcher", "LHP", "RHP", "PH", "SP/RP"):
            self.assertEqual(utils.normalize_pos(raw), "P")

    def test_saving_a_two_way_code_does_not_collapse_it(self):
        player = models.Player.objects.create(name="Two Way", position="DH/SP")
        self.assertEqual(player.position, "DH-P")
        player.position = "OF-P"
        player.save()
        self.assertEqual(player.position, "OF-P")

    def test_a_dh_who_pitches_is_a_designated_hitter(self):
        player = models.Player(name="Two Way", position="DH-P")
        self.assertEqual(cards.playing_primary(None, player), "DH")
        self.assertEqual(cards.playing_primary(models.Card(primary_position="CF"), player), "CF")


class PromoteTwoWayTestCase(TestCase):
    def _card(self, player, season, pa, primary, hitting=True, pitching=True):
        return models.Card.objects.create(
            player=player,
            season=season,
            plate_appearances=pa,
            primary_position=primary,
            hitter_rates={"k": 0.2} if hitting else None,
            pitcher_rates={"k": 0.25} if pitching else None,
        )

    def test_a_full_batting_season_makes_a_pitcher_two_way(self):
        designated = models.Player.objects.create(name="Designated", position="P")
        outfielder = models.Player.objects.create(name="Outfield", position="P")
        infielder = models.Player.objects.create(name="Infield", position="P")
        self._card(designated, 2025, 600, "DH")
        self._card(outfielder, 2025, utils.TWO_WAY_PLATE_APPEARANCES, "CF")
        self._card(infielder, 2025, 400, "SS")

        utils.promote_two_way_pitchers()

        designated.refresh_from_db()
        outfielder.refresh_from_db()
        infielder.refresh_from_db()
        self.assertEqual(designated.position, "DH-P")
        self.assertEqual(outfielder.position, "OF-P")
        self.assertEqual(infielder.position, "IF-P")

    def test_a_short_batting_line_stays_a_pitcher(self):
        mop = models.Player.objects.create(name="Mop Up", position="P")
        self._card(mop, 2025, utils.TWO_WAY_PLATE_APPEARANCES - 1, "DH")
        utils.promote_two_way_pitchers()
        mop.refresh_from_db()
        self.assertEqual(mop.position, "P")

    def test_an_older_two_way_season_does_not_reclassify_a_current_pitcher(self):
        former = models.Player.objects.create(name="Former", position="P")
        self._card(former, 2024, 500, "DH")
        self._card(former, 2025, 8, "DH")
        pitcher = models.Player.objects.create(name="Now Pitcher", position="P")
        self._card(pitcher, 2024, 500, "OF")
        self._card(pitcher, 2025, None, None, hitting=False)
        hitter = models.Player.objects.create(name="Hitter", position="OF")
        self._card(hitter, 2025, 600, "DH")

        utils.promote_two_way_pitchers()

        former.refresh_from_db()
        pitcher.refresh_from_db()
        hitter.refresh_from_db()
        self.assertEqual(former.position, "P")
        self.assertEqual(pitcher.position, "P")
        self.assertEqual(hitter.position, "OF")


@override_settings(CURRENT_SEASON=2026)
class TwoWayPlayerPageTestCase(TestCase):
    def _player(self, name, position):
        player = models.Player.objects.create(name=name, position=position)
        models.PlayerStatSeason.objects.create(
            player=player,
            season=2025,
            classification="1-mlb",
            hit_stats={"pa": 180, "k_pct": 0.2, "bb_pct": 0.08},
            pitch_stats={"g": 20, "ip": 120.0},
        )
        return player

    def test_a_two_way_player_page_shows_hitting_and_pitching(self):
        player = self._player("Two Way", "DH-P")
        body = logged_in_client().get(f"/players/{player.id}/").content.decode()
        self.assertIn("Hitting Stats", body)
        self.assertIn("Pitching Stats", body)

    def test_a_pitcher_page_shows_pitching_only(self):
        player = self._player("Pitcher", "P")
        body = logged_in_client().get(f"/players/{player.id}/").content.decode()
        self.assertNotIn("Hitting Stats", body)
        self.assertIn("Pitching Stats", body)

    def test_a_hitter_page_shows_hitting_only(self):
        player = self._player("Hitter", "OF")
        body = logged_in_client().get(f"/players/{player.id}/").content.decode()
        self.assertIn("Hitting Stats", body)
        self.assertNotIn("Pitching Stats", body)
