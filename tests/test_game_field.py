# ABOUTME: Tests the SNES field JSON, the HTML line score, and the kit composer the game page loads.
# ABOUTME: The page tests play a real engine game and check the call buttons and the substitution modals.

import json
import os
import subprocess
from pathlib import Path

from django.test import SimpleTestCase, TestCase, override_settings

from tests import game_fixtures as gf
from ulmg import game_field, models, sim_game

Event = models.GameEvent
AWAY, HOME = sim_game.AWAY, sim_game.HOME

STRIKEOUT = {"k": 1.0, "bb": 0.0, "hbp": 0.0, "single": 0.0, "double": 0.0, "triple": 0.0, "hr": 0.0, "bip_out": 0.0}
ROOT = Path(__file__).resolve().parent.parent


class FieldGeometryTest(SimpleTestCase):
    def test_fielding_value_is_the_card_runs_with_a_sign(self):
        self.assertEqual(game_field.fielding_label(0.15), "+1.5")
        self.assertEqual(game_field.fielding_label(0.4), "+4.0")
        self.assertEqual(game_field.fielding_label(-0.2), "-2.0")
        self.assertEqual(game_field.fielding_label(0), "0.0")

    def test_an_error_lands_as_a_ground_ball_and_says_error(self):
        shown = game_field.result_banner(
            {"outcome": "reached_on_error", "batter_id": "4", "count": {"balls": 1, "strikes": 1}}
        )
        self.assertEqual(shown["label"], "ERROR")
        self.assertEqual(shown["kind"], "ground")
        self.assertIsNotNone(shown["x"])

    def test_a_right_handed_batter_stands_on_the_third_base_side(self):
        self.assertEqual(game_field.batter_box("R", "R"), "left")
        self.assertFalse(game_field.batter_flip("left"))

    def test_a_left_handed_batter_stands_on_the_first_base_side(self):
        self.assertEqual(game_field.batter_box("L", "L"), "right")
        self.assertTrue(game_field.batter_flip("right"))

    def test_a_switch_hitter_stands_opposite_the_pitcher(self):
        self.assertEqual(game_field.batter_box("S", "R"), "right")
        self.assertEqual(game_field.batter_box("S", "L"), "left")
        self.assertEqual(game_field.batter_box("S", None), "left")

    def test_a_single_is_a_line_drive_in_world_space(self):
        ball = game_field.ball_track({"outcome": "single", "batter_id": "9", "count": {"balls": 1, "strikes": 2}})
        self.assertEqual(ball["kind"], "line")
        self.assertEqual(ball["label"], "SINGLE")
        self.assertIn((ball["x"], ball["z"]), game_field.LANDINGS["single"])
        self.assertEqual(ball["height_ft"], game_field.HEIGHT_FT["line"])
        self.assertEqual(ball["count"], "1-2")

    def test_the_same_batted_ball_lands_in_the_same_place(self):
        result = {"outcome": "line_out", "batter_id": "4", "count": {"balls": 0, "strikes": 1}}
        self.assertEqual(game_field.ball_track(result)["z"], game_field.ball_track(result)["z"])

    def test_a_strikeout_has_a_banner_and_no_landing(self):
        self.assertIsNone(game_field.ball_track({"outcome": "strikeout", "batter_id": "1", "count": {"balls": 0, "strikes": 3}}))
        shown = game_field.result_banner({"outcome": "strikeout", "count": {"balls": 0, "strikes": 3}})
        self.assertEqual(shown["label"], "STRIKEOUT")
        self.assertIsNone(shown["z"])

    def test_the_logical_field_is_the_kit_320_by_180(self):
        self.assertEqual(game_field.LOGICAL, {"width": 320, "height": 180})
        self.assertEqual(game_field.MIN_SCALE, 3)

    def test_world_positions_match_the_kit(self):
        self.assertEqual(game_field.POS["CF"], (0, 315))
        self.assertEqual(game_field.POS["P"], (0, 60.5))
        self.assertLess(game_field.POS["3B"][0], 0)
        self.assertGreater(game_field.POS["1B"][0], 0)

    def test_skin_is_stable_for_a_player(self):
        self.assertEqual(game_field.skin_for(4), game_field.skin_for(4))
        self.assertIn(game_field.skin_for(4), game_field.SKINS)
        self.assertEqual(len({game_field.skin_for(i) for i in range(6)}), 3)

    def test_the_composer_draws_kit_sprites_at_an_integer_scale(self):
        result = subprocess.run(
            ["node", str(ROOT / "tests" / "js" / "test_game_field.mjs")],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("ok", result.stdout)


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

    def field_data(self, response):
        html = response.content.decode()
        blob = html.split('id="game-field-data"', 1)[1].split(">", 1)[1].split("</script>", 1)[0]
        return json.loads(blob)

    def test_the_field_names_every_fielder_with_his_position_and_fielding_value(self):
        self.post("open", seats="away,home")
        response = self.client.get(self.url)
        field = self.field_data(response)
        catcher = next(f for f in field["fielders"] if f["position"] == "C")
        self.assertEqual(catcher["name"], self.home.catcher.name)
        self.assertEqual(catcher["fielding"], "+4.0")
        self.assertEqual(catcher["sprite"], "catcher")
        self.assertEqual((catcher["x"], catcher["z"]), game_field.POS["C"])
        names = {f["name"] for f in field["fielders"]}
        for fielder in self.home.fielders:
            self.assertIn(fielder.name, names)
        self.assertNotIn(self.home.hitters[-1].name, names)
        self.assertContains(response, 'src="/static/ulmg/game_field.js"')

    @override_settings(STATIC_URL="https://static-theulmg.nyc3.cdn.digitaloceanspaces.com/static/")
    def test_the_field_script_stays_on_this_site_when_other_static_files_use_the_cdn(self):
        self.post("open", seats="away,home")
        response = self.client.get(self.url)
        self.assertContains(response, 'src="/static/ulmg/game_field.js"')
        self.assertNotContains(
            response,
            "https://static-theulmg.nyc3.cdn.digitaloceanspaces.com/static/ulmg/game_field.js",
        )

    def test_the_mound_shows_xfip_pitches_and_fatigue(self):
        self.post("open", seats="away,home")
        starter = self.home.starters[0]
        row = models.PlayerStatSeason.objects.get(player=starter, season=gf.CARD_SEASON, classification="1-mlb")
        row.pitch_stats = {**row.pitch_stats, "xfip": 3.37}
        row.save(update_fields=["pitch_stats"])
        response = self.client.get(self.url)
        pitcher = self.field_data(response)["pitcher"]
        fatigue = self.log().state[HOME]["fatigue"][str(starter.id)]
        self.assertEqual(pitcher["name"], starter.name)
        self.assertEqual(pitcher["xfip"], "3.37")
        self.assertEqual(pitcher["pitches"], fatigue["pitches"])
        self.assertEqual(pitcher["effort"], fatigue["effort"])
        self.assertEqual(pitcher["ceiling"], fatigue["ceiling"])
        self.assertEqual(pitcher["sprite"], "pitch_set")

    def test_the_batter_stands_on_the_side_he_hits_from(self):
        self.post("open", seats="away,home")
        leadoff = self.road.hitters[0]
        response = self.client.get(self.url)
        html = response.content.decode()
        self.assertIn('id="game-field-data"', html)
        self.assertIn("min-height: 540px", html)
        batter = self.field_data(response)["batter"]
        self.assertEqual(batter["box"], "left")
        self.assertFalse(batter["flip"])

        leadoff.bats = "L"
        leadoff.save(update_fields=["bats"])
        batter = self.field_data(self.client.get(self.url))["batter"]
        self.assertEqual(batter["box"], "right")
        self.assertTrue(batter["flip"])
        self.assertEqual(batter["hand"], "L")

        leadoff.bats = "S"
        leadoff.save(update_fields=["bats"])
        batter = self.field_data(self.client.get(self.url))["batter"]
        self.assertEqual(batter["box"], "right")
        self.assertTrue(batter["flip"])

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

    def test_a_ball_in_play_has_a_landing_and_a_strikeout_does_not(self):
        self.post("open", seats="away,home")
        gf.set_rates([self.road.hitters[0]], gf.HOME_RUN_RATES)
        response = self.post("step", expected=self.expected())
        field = self.field_data(response)
        ball = game_field.ball_track(self.log().state["last_result"])
        self.assertEqual(ball["kind"], "fly")
        self.assertEqual(field["banner"]["outcome"], "home_run")
        self.assertEqual(field["banner"]["z"], ball["z"])
        self.assertContains(response, "HOME RUN")

        gf.set_rates(self.road.hitters[1:2], STRIKEOUT)
        response = self.post("step", expected=self.expected())
        field = self.field_data(response)
        self.assertIsNone(field["banner"]["z"])
        self.assertContains(response, "STRIKEOUT")

    def test_substitution_buttons_open_modals_of_the_available_players(self):
        self.post("open", seats="away,home")
        self.post("step", expected=self.expected())
        response = self.client.get(self.url)
        html = response.content.decode()
        self.assertIn(">Substitution<", html)
        self.assertNotIn(">Offensive substitution<", html)
        self.assertNotIn(">Defensive substitution<", html)
        self.assertLess(html.find('class="game-scoreboard'), html.find('class="game-field"'))
        self.assertLess(html.find('class="game-field"'), html.find("Play the next plate appearance"))
        modal = html.split('id="substitution"', 1)[1].split('id="game-after-modals"', 1)[0]
        self.assertIn(f'action="/games/{self.game.id}/pinch_hit/"', modal)
        self.assertIn(f'value="{self.road.bench[0].id}"', modal)
        self.assertIn(f'action="/games/{self.game.id}/pitcher/"', modal)
        self.assertIn(f'value="{self.home.relievers[0].id}"', modal)
        self.assertIn(f'action="/games/{self.game.id}/defense/"', modal)
        self.assertIn(f'value="{self.home.bench[0].id}"', modal)
        self.assertIn(f'action="/games/{self.game.id}/positions/"', modal)

    def test_the_home_club_is_home_whites_and_the_road_club_is_away(self):
        self.post("open", seats="away,home")
        field = self.field_data(self.client.get(self.url))
        catcher = next(f for f in field["fielders"] if f["position"] == "C")
        self.assertEqual(catcher["team"], "home")
        self.assertEqual(field["batter"]["team"], "away")
        self.assertIn(catcher["skin"], game_field.SKINS)

    def test_the_home_field_plate_and_rules_reach_the_page(self):
        venue = models.Venue.objects.create(
            name="Coors Field",
            mlb_team="Rockies",
            mlb_venue_id="19",
            mlb_venue_url="u",
            team=self.home.team,
            pf_hr=119,
            rules={"distances_ft": {"center": 415}, "roof": "open", "ground_rules": "The ball carries."},
            sprites={"version": 1, "plate_svg": '<g id="coors-plate"></g>'},
        )
        self.home.team.home_field = venue
        self.home.team.save()
        self.post("open", seats="away,home")
        field = self.field_data(self.client.get(self.url))
        self.assertEqual(field["park"]["name"], "Coors Field")
        self.assertEqual(field["park"]["scores"]["home_run"], 119)
        self.assertEqual(field["park"]["rules"]["distances_ft"]["center"], 415)
        self.assertEqual(field["park"]["rules"]["distances_ft"]["lf_line"], 330)
        self.assertEqual(field["park"]["rules"]["ground_rules"], "The ball carries.")
        self.assertEqual(field["park"]["sprites"]["plate_svg"], '<g id="coors-plate"></g>')

    def test_infield_names_are_tagged_from_world_positions(self):
        self.post("open", seats="away,home")
        by_pos = {f["position"]: f for f in self.field_data(self.client.get(self.url))["fielders"]}
        self.assertLess(by_pos["SS"]["x"], 0)
        self.assertGreater(by_pos["1B"]["x"], 0)
        self.assertEqual((by_pos["SS"]["x"], by_pos["SS"]["z"]), game_field.POS["SS"])
        self.assertEqual((by_pos["1B"]["x"], by_pos["1B"]["z"]), game_field.POS["1B"])

    def test_the_line_score_is_html_with_nine_innings_and_dashes(self):
        self.post("open", seats="away,home")
        gf.set_rates([self.road.hitters[0]], gf.HOME_RUN_RATES)
        html = self.post("step", expected=self.expected()).content.decode()
        stage = html.split('class="game-stage"', 1)[1].split('class="game-below"', 1)[0]
        self.assertLess(stage.find('class="line-score'), stage.find('class="game-field"'))
        self.assertLess(html.find('class="line-score'), html.find("Play-by-play"))
        self.assertNotIn("line-score", html.split('id="game-field-data"', 1)[1].split("</script>", 1)[0])
        table = stage.split('class="line-score', 1)[1].split("</table>", 1)[0]
        self.assertIn(">1<", table)
        self.assertIn(">9<", table)
        road = table.split(self.road.team.abbreviation, 1)[1].split("</tr>", 1)[0]
        home = table.split(self.home.team.abbreviation, 1)[1].split("</tr>", 1)[0]
        self.assertIn(">1<", road)
        self.assertIn(">-</td>", home)
        self.assertNotIn(">X<", home)

    def test_batting_calls_wait_for_the_manager_who_is_batting(self):
        # Top of the first, the home manager is on the mound. Bunt, steal and hit and run are the batter's.
        self.post("open", seats="home")
        response = self.client.get(self.url)
        html = response.content.decode()
        self.assertContains(response, "Play the next plate appearance")
        self.assertContains(response, ">Substitution<")
        self.assertNotContains(response, 'value="bunt"')
        self.assertNotContains(response, 'value="steal"')
        self.assertNotContains(response, 'value="hit_and_run"')
        self.assertLess(html.find('class="game-scoreboard'), html.find(">Substitution<"))

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
        single = {"k": 0.0, "bb": 0.0, "hbp": 0.0, "single": 1.0, "double": 0.0, "triple": 0.0, "hr": 0.0, "bip_out": 0.0}
        gf.set_rates([self.road.hitters[0]], single)
        out = "/opt/cursor/artifacts"
        os.makedirs(out, exist_ok=True)
        self.client.force_login(self.tester)
        before = self.client.get(self.url)
        open(f"{out}/game-before.html", "w").write(before.content.decode())
        response = self.post("step", expected=self.expected())
        open(f"{out}/game-line-drive.html", "w").write(response.content.decode())
        homer = self.post("step", expected=self.expected())
        open(f"{out}/game-line-score.html", "w").write(homer.content.decode())
        print("OUTCOME", self.log().state["last_result"]["outcome"])
