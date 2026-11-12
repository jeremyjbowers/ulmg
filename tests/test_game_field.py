# ABOUTME: Tests the video-game field: fielder plates, the pitcher's mound card, the batter's box and the ball track.
# ABOUTME: The page tests play a real engine game and check the call buttons and the substitution modals.

import os

from django.test import SimpleTestCase, TestCase

from tests import game_fixtures as gf
from ulmg import game_field, models, sim_game

Event = models.GameEvent
AWAY, HOME = sim_game.AWAY, sim_game.HOME

STRIKEOUT = {"k": 1.0, "bb": 0.0, "hbp": 0.0, "single": 0.0, "double": 0.0, "triple": 0.0, "hr": 0.0, "bip_out": 0.0}


class FieldGeometryTest(SimpleTestCase):
    def test_fielding_value_is_the_card_runs_with_a_sign(self):
        self.assertEqual(game_field.fielding_label(0.15), "+1.5")
        self.assertEqual(game_field.fielding_label(0.4), "+4.0")
        self.assertEqual(game_field.fielding_label(-0.2), "-2.0")
        self.assertEqual(game_field.fielding_label(0), "0.0")

    def test_a_right_handed_batter_stands_on_the_third_base_side(self):
        # From behind the plate, the right-handed box is on the left of the screen.
        self.assertEqual(game_field.batter_box("R", "R"), "left")
        self.assertLess(game_field.BATTER_BOXES["left"][0], game_field.HOME[0])

    def test_a_left_handed_batter_stands_on_the_first_base_side(self):
        self.assertEqual(game_field.batter_box("L", "L"), "right")
        self.assertGreater(game_field.BATTER_BOXES["right"][0], game_field.HOME[0])

    def test_a_switch_hitter_stands_opposite_the_pitcher(self):
        self.assertEqual(game_field.batter_box("S", "R"), "right")
        self.assertEqual(game_field.batter_box("S", "L"), "left")
        self.assertEqual(game_field.batter_box("S", None), "left")

    def test_a_single_is_a_line_drive_with_a_track_from_home(self):
        ball = game_field.ball_track({"outcome": "single", "batter_id": "9", "count": {"balls": 1, "strikes": 2}})
        self.assertEqual(ball["kind"], "line")
        self.assertEqual(ball["label"], "SINGLE")
        self.assertTrue(ball["path"].startswith(f"M {game_field.CONTACT[0]},{game_field.CONTACT[1]} Q "))
        self.assertEqual(ball["count"], "1-2")

    def test_the_same_batted_ball_lands_in_the_same_place(self):
        result = {"outcome": "line_out", "batter_id": "4", "count": {"balls": 0, "strikes": 1}}
        self.assertEqual(game_field.ball_track(result)["path"], game_field.ball_track(result)["path"])

    def test_a_strikeout_has_a_banner_and_no_track(self):
        self.assertIsNone(game_field.ball_track({"outcome": "strikeout", "batter_id": "1", "count": {"balls": 0, "strikes": 3}}))
        shown = game_field.result_banner({"outcome": "strikeout", "count": {"balls": 0, "strikes": 3}})
        self.assertEqual(shown["label"], "STRIKEOUT")
        self.assertIsNone(shown["path"])

    def test_the_result_sits_on_the_marquee_below_every_batted_ball(self):
        # The word used to share the grass with the landing, so a single sat on top of SINGLE.
        for outcome in game_field.LANDINGS:
            ball = game_field.ball_track({"outcome": outcome, "batter_id": "9", "count": {"balls": 1, "strikes": 2}})
            self.assertLess(ball["y"], game_field.PLAY_HEIGHT)
        self.assertGreaterEqual(game_field.BANNER_Y, game_field.PLAY_HEIGHT)
        self.assertGreater(game_field.HEIGHT, game_field.BANNER_Y)


class GameFieldPageTest(gf.EngineMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        gf.create_game_season(cls)

    def setUp(self):
        self.next_seed = gf.seeds()
        self.url = f"/games/{self.game.id}/"

    def post(self, action, user=None, **data):
        self.client.force_login(user or self.tester)
        return self.client.post(f"{self.url}{action}/", data, follow=True)

    def log(self):
        return models.GameLog.objects.get(game=self.game)

    def expected(self):
        return sim_game.Play(self.log()).sequence

    def field_markup(self, response):
        html = response.content.decode()
        return html.split('class="game-field"', 1)[1].split("</svg>", 1)[0]

    def test_the_field_names_every_fielder_with_his_position_and_fielding_value(self):
        self.post("open", seats="away,home")
        response = self.client.get(self.url)
        field = self.field_markup(response)
        self.assertIn(self.home.catcher.name, field)
        self.assertIn('data-position="C"', field)
        self.assertIn('data-fielding="+4.0"', field)
        for fielder in self.home.fielders:
            self.assertIn(fielder.name, field)
            self.assertIn('data-fielding="+1.5"', field)
        self.assertNotIn(f'data-name="{self.home.hitters[-1].name}"', field)

    def test_the_mound_shows_xfip_pitches_and_fatigue(self):
        self.post("open", seats="away,home")
        starter = self.home.starters[0]
        row = models.PlayerStatSeason.objects.get(player=starter, season=gf.CARD_SEASON, classification="1-mlb")
        row.pitch_stats = {**row.pitch_stats, "xfip": 3.37}
        row.save(update_fields=["pitch_stats"])
        response = self.client.get(self.url)
        field = self.field_markup(response)
        fatigue = self.log().state[HOME]["fatigue"][str(starter.id)]
        self.assertIn(starter.name, field)
        self.assertIn('data-xfip="3.37"', field)
        self.assertIn(f'data-pitches="{fatigue["pitches"]}"', field)
        self.assertIn(f'data-effort="{fatigue["effort"]}"', field)
        self.assertIn(f'data-ceiling="{fatigue["ceiling"]}"', field)
        self.assertIn("xFIP", field)
        self.assertIn("pitches", field)

    def test_the_batter_stands_on_the_side_he_hits_from(self):
        self.post("open", seats="away,home")
        leadoff = self.road.hitters[0]
        response = self.client.get(self.url)
        # No plate appearance yet, so the screen is the grass only. The marquee appears with the result.
        self.assertIn(f'viewBox="0 0 {game_field.WIDTH} {game_field.PLAY_HEIGHT}"', response.content.decode())
        self.assertIn('data-box="left"', self.field_markup(response))
        self.assertIn(f'translate({game_field.BATTER_BOXES["left"][0]},', self.field_markup(response))

        leadoff.bats = "L"
        leadoff.save(update_fields=["bats"])
        response = self.client.get(self.url)
        self.assertIn('data-box="right"', self.field_markup(response))
        self.assertIn(f'translate({game_field.BATTER_BOXES["right"][0]},', self.field_markup(response))

        leadoff.bats = "S"
        leadoff.save(update_fields=["bats"])
        response = self.client.get(self.url)
        self.assertIn('data-box="right"', self.field_markup(response))

    def test_hit_and_run_and_steal_are_buttons_that_resolve_the_plate_appearance(self):
        self.post("open", seats="away,home")
        response = self.client.get(self.url)
        self.assertContains(response, 'value="hit_and_run"')
        self.assertContains(response, 'value="steal"')
        self.assertContains(response, "Play the next plate appearance")
        response = self.post("step", expected=self.expected(), call="hit_and_run")
        self.assertEqual(gf.events(self.log(), Event.CALL)[-1].payload["call"], "hit_and_run")
        self.assertContains(response, "calls hit and run")
        response = self.post("step", expected=self.expected(), call="steal")
        self.assertEqual(gf.events(self.log(), Event.CALL)[-1].payload["call"], "steal")

    def test_a_ball_in_play_draws_a_track_and_a_strikeout_does_not(self):
        self.post("open", seats="away,home")
        # A home run is in play no matter the defense. A strikeout never is.
        gf.set_rates([self.road.hitters[0]], gf.HOME_RUN_RATES)
        response = self.post("step", expected=self.expected())
        field = self.field_markup(response)
        ball = game_field.ball_track(self.log().state["last_result"])
        self.assertIn(f'viewBox="0 0 {game_field.WIDTH} {game_field.HEIGHT}"', field)
        self.assertEqual(ball["kind"], "fly")
        self.assertIn('class="ball-track ball-track-fly"', field)
        self.assertIn('data-kind="fly"', field)
        self.assertIn('data-outcome="home_run"', field)
        self.assertIn(ball["path"], field)
        self.assertIn("HOME RUN", field)

        gf.set_rates(self.road.hitters[1:2], STRIKEOUT)
        response = self.post("step", expected=self.expected())
        field = self.field_markup(response)
        self.assertNotIn("ball-track", field)
        self.assertIn("STRIKEOUT", field)

    def test_substitution_buttons_open_modals_of_the_available_players(self):
        self.post("open", seats="away,home")
        self.post("step", expected=self.expected())
        response = self.client.get(self.url)
        html = response.content.decode()
        self.assertIn(">Offensive substitution<", html)
        self.assertIn(">Pitching change<", html)
        self.assertIn(">Defensive substitution<", html)
        offense = html.split('id="offense-sub"', 1)[1].split('id="pitching-change"', 1)[0]
        pitching = html.split('id="pitching-change"', 1)[1].split('id="defense-sub"', 1)[0]
        defense = html.split('id="defense-sub"', 1)[1].split('id="game-after-modals"', 1)[0]
        self.assertIn(f'action="/games/{self.game.id}/pinch_hit/"', offense)
        self.assertIn(f'value="{self.road.bench[0].id}"', offense)
        self.assertIn(f'action="/games/{self.game.id}/pitcher/"', pitching)
        self.assertIn(f'value="{self.home.relievers[0].id}"', pitching)
        self.assertIn(f'action="/games/{self.game.id}/defense/"', defense)
        self.assertIn(f'value="{self.home.bench[0].id}"', defense)
        self.assertIn(f'action="/games/{self.game.id}/positions/"', defense)

    def test_write_preview(self):
        if os.environ.get("SAVE_GAME_HTML") != "1":
            return
        self.post("open", seats="away,home")
        names = {
            self.home.catcher: ("Sean", "Murphy"),
            self.home.starters[0]: ("Logan", "Webb"),
            self.road.hitters[0]: ("Mookie", "Betts"),
            self.road.hitters[1]: ("Kyle", "Schwarber"),
        }
        for fielder, name in zip(
            self.home.fielders,
            [("Freddie", "Freeman"), ("Gleyber", "Torres"), ("Austin", "Riley"), ("Dansby", "Swanson"), ("Ian", "Happ"), ("Pete", "Crow"), ("Randy", "Arozarena")],
        ):
            names[fielder] = name
        for player, (first, last) in names.items():
            player.first_name = first
            player.last_name = last
            player.name = f"{first} {last}"
            player.save()
        self.road.hitters[1].bats = "L"
        self.road.hitters[1].save(update_fields=["bats"])
        starter = self.home.starters[0]
        row = models.PlayerStatSeason.objects.get(player=starter, season=gf.CARD_SEASON, classification="1-mlb")
        row.pitch_stats = {**row.pitch_stats, "xfip": 3.37}
        row.save(update_fields=["pitch_stats"])
        gf.set_rates(self.road.hitters, gf.HOME_RUN_RATES)
        # A single is the line drive. Home-run rates are certain, so swap the leadoff to a pure single.
        single = {"k": 0.0, "bb": 0.0, "hbp": 0.0, "single": 1.0, "double": 0.0, "triple": 0.0, "hr": 0.0, "bip_out": 0.0}
        gf.set_rates([self.road.hitters[0]], single)
        out = "/opt/cursor/artifacts"
        os.makedirs(out, exist_ok=True)
        self.client.force_login(self.tester)
        before = self.client.get(self.url)
        open(f"{out}/game-before.html", "w").write(before.content.decode())
        response = self.post("step", expected=self.expected())
        open(f"{out}/game-line-drive.html", "w").write(response.content.decode())
        print("OUTCOME", self.log().state["last_result"]["outcome"])
