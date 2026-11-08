# ABOUTME: Tests for platoon splits: regression math, split download/load, card generation, step rates, display.
# ABOUTME: Split rows use FanGraphs splits-tool column names with constructed values; the engine test runs the real binary.
import json
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from io import StringIO

from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import Client, SimpleTestCase, TestCase, override_settings

from tests.engine_process import FIXTURE_PATH, EngineProcess, build_engine
from tests.test_cards import FG_HITTER_ROW, FG_PITCHER_ROW, processed
from ulmg import cards, engine_client, models, utils
from ulmg.management.commands import live_download_fg_splits

FIXTURE_SPLITS_DIR = os.path.join(os.path.dirname(__file__), "fixtures", "fg_mlb_splits_sample")

HITTER_KEYS = ["k", "bb", "hbp", "single", "double", "triple", "hr", "bip_out"]
PITCHER_KEYS = ["k", "bb", "hbp", "hr", "h"]


def split_row(key):
    with open(os.path.join(FIXTURE_SPLITS_DIR, f"fg_mlb_splits_{key}.json")) as f:
        return processed(json.load(f)[0])


class RegressionConstantTestCase(SimpleTestCase):
    def test_regression_constant(self):
        self.assertEqual(cards.PLATOON_REGRESSION_PA, 400)


class RegressSplitTestCase(SimpleTestCase):
    def setUp(self):
        self.overall = cards.hitter_rates(processed(FG_HITTER_ROW))
        self.vs_lhp = cards.hitter_rates(split_row("bat_vs_lhp"))

    def test_each_rate_is_weighted_toward_overall(self):
        regressed = cards.regress_split(self.vs_lhp, self.overall, 150)
        for key in HITTER_KEYS:
            expected = (150 * self.vs_lhp[key] + 400 * self.overall[key]) / (150 + 400)
            self.assertAlmostEqual(regressed[key], expected)

    def test_strikeout_rate_by_hand(self):
        regressed = cards.regress_split(self.vs_lhp, self.overall, 150)
        self.assertAlmostEqual(regressed["k"], (40 + 400 * 0.2) / 550)

    def test_hitter_rates_sum_to_one(self):
        regressed = cards.regress_split(self.vs_lhp, self.overall, 150)
        self.assertEqual(list(regressed.keys()), HITTER_KEYS)
        self.assertAlmostEqual(sum(regressed.values()), 1.0)

    def test_renormalizes_rates_that_do_not_sum_to_one(self):
        lopsided = dict(self.vs_lhp, bip_out=self.vs_lhp["bip_out"] + 0.1)
        regressed = cards.regress_split(lopsided, self.overall, 150)
        self.assertAlmostEqual(sum(regressed.values()), 1.0)
        raw_k = (150 * lopsided["k"] + 400 * self.overall["k"]) / 550
        self.assertLess(regressed["k"], raw_k)

    def test_a_larger_sample_moves_further_from_overall(self):
        small = cards.regress_split(self.vs_lhp, self.overall, 50)
        large = cards.regress_split(self.vs_lhp, self.overall, 5000)
        self.assertLess(abs(small["k"] - self.vs_lhp["k"]), abs(self.overall["k"] - self.vs_lhp["k"]))
        self.assertLess(abs(large["k"] - self.vs_lhp["k"]), abs(small["k"] - self.vs_lhp["k"]))

    def test_no_plate_appearances_is_the_overall_card(self):
        self.assertEqual(cards.regress_split(None, self.overall, 0), self.overall)
        self.assertEqual(cards.regress_split(self.vs_lhp, self.overall, 0), self.overall)

    def test_pitcher_rates_keep_the_out_remainder(self):
        overall = cards.pitcher_rates(processed(FG_PITCHER_ROW))
        vs_lhh = cards.pitcher_rates(split_row("pit_vs_lhh"))
        regressed = cards.regress_split(vs_lhh, overall, 350)
        self.assertEqual(list(regressed.keys()), PITCHER_KEYS)
        for key in PITCHER_KEYS:
            self.assertAlmostEqual(regressed[key], (350 * vs_lhh[key] + 400 * overall[key]) / 750)
        out_remainder = (350 * (1 - sum(vs_lhh.values())) + 400 * (1 - sum(overall.values()))) / 750
        self.assertAlmostEqual(sum(regressed.values()) + out_remainder, 1.0)


class SplitRatesFromStatsTestCase(SimpleTestCase):
    def test_hitter_split_uses_split_plate_appearances(self):
        overall = cards.hitter_rates(processed(FG_HITTER_ROW))
        rates = cards.hitter_split_rates(split_row("bat_vs_rhp"), overall)
        self.assertAlmostEqual(rates["k"], (80 + 400 * 0.2) / 850)
        self.assertAlmostEqual(sum(rates.values()), 1.0)

    def test_pitcher_split_uses_split_batters_faced(self):
        overall = cards.pitcher_rates(processed(FG_PITCHER_ROW))
        rates = cards.pitcher_split_rates(split_row("pit_vs_rhh"), overall)
        self.assertAlmostEqual(rates["k"], (120 + 400 * 0.25) / 850)
        self.assertAlmostEqual(rates["h"], ((85 - 12) + 400 * 136 / 800) / 850)

    def test_missing_split_is_the_overall_card(self):
        overall = cards.hitter_rates(processed(FG_HITTER_ROW))
        self.assertEqual(cards.hitter_split_rates(None, overall), overall)
        self.assertEqual(cards.hitter_split_rates(split_row("bat_vs_lhp") | {"pa": 0}, overall), overall)
        pitcher_overall = cards.pitcher_rates(processed(FG_PITCHER_ROW))
        self.assertEqual(cards.pitcher_split_rates({}, pitcher_overall), pitcher_overall)

    def test_no_overall_card_gives_no_split(self):
        self.assertIsNone(cards.hitter_split_rates(split_row("bat_vs_lhp"), None))


def platoon_cards():
    batter = models.Card(
        hitter_rates={"k": 0.2, "bb": 0.1, "hbp": 0.01, "single": 0.15, "double": 0.05, "triple": 0.005, "hr": 0.04, "bip_out": 0.445},
        hitter_rates_vs_lhp={"k": 0.3, "bb": 0.06, "hbp": 0.01, "single": 0.12, "double": 0.04, "triple": 0.005, "hr": 0.02, "bip_out": 0.445},
        hitter_rates_vs_rhp={"k": 0.15, "bb": 0.12, "hbp": 0.01, "single": 0.16, "double": 0.055, "triple": 0.005, "hr": 0.05, "bip_out": 0.45},
    )
    pitcher = models.Card(
        pitcher_rates={"k": 0.25, "bb": 0.07, "hbp": 0.01, "hr": 0.03, "h": 0.17},
        pitcher_rates_vs_lhh={"k": 0.18, "bb": 0.09, "hbp": 0.01, "hr": 0.035, "h": 0.2},
        pitcher_rates_vs_rhh={"k": 0.31, "bb": 0.055, "hbp": 0.01, "hr": 0.025, "h": 0.15},
    )
    return batter, pitcher


class BattingSideTestCase(SimpleTestCase):
    def test_left_and_right_handed_batters_keep_their_side(self):
        self.assertEqual(cards.batting_side("L", "L"), "L")
        self.assertEqual(cards.batting_side("R", "L"), "R")

    def test_switch_hitter_bats_opposite_the_pitcher(self):
        self.assertEqual(cards.batting_side("S", "L"), "R")
        self.assertEqual(cards.batting_side("S", "R"), "L")

    def test_unknown_sides(self):
        self.assertIsNone(cards.batting_side(None, "R"))
        self.assertIsNone(cards.batting_side("S", None))


class PlateAppearanceRatesTestCase(SimpleTestCase):
    def setUp(self):
        self.batter, self.pitcher = platoon_cards()

    def test_lefty_batter_against_a_right_hander(self):
        rates = cards.plate_appearance_rates(self.batter, self.pitcher, "L", "R")
        self.assertEqual(rates["hitter_rates"], self.batter.hitter_rates_vs_rhp)
        self.assertEqual(rates["pitcher_rates"], self.pitcher.pitcher_rates_vs_lhh)

    def test_righty_batter_against_a_left_hander(self):
        rates = cards.plate_appearance_rates(self.batter, self.pitcher, "R", "L")
        self.assertEqual(rates["hitter_rates"], self.batter.hitter_rates_vs_lhp)
        self.assertEqual(rates["pitcher_rates"], self.pitcher.pitcher_rates_vs_rhh)

    def test_same_side_matchups(self):
        rates = cards.plate_appearance_rates(self.batter, self.pitcher, "L", "L")
        self.assertEqual(rates["hitter_rates"], self.batter.hitter_rates_vs_lhp)
        self.assertEqual(rates["pitcher_rates"], self.pitcher.pitcher_rates_vs_lhh)
        rates = cards.plate_appearance_rates(self.batter, self.pitcher, "R", "R")
        self.assertEqual(rates["hitter_rates"], self.batter.hitter_rates_vs_rhp)
        self.assertEqual(rates["pitcher_rates"], self.pitcher.pitcher_rates_vs_rhh)

    def test_switch_hitter_against_a_left_hander_bats_right(self):
        rates = cards.plate_appearance_rates(self.batter, self.pitcher, "S", "L")
        self.assertEqual(rates["hitter_rates"], self.batter.hitter_rates_vs_lhp)
        self.assertEqual(rates["pitcher_rates"], self.pitcher.pitcher_rates_vs_rhh)

    def test_switch_hitter_against_a_right_hander_bats_left(self):
        rates = cards.plate_appearance_rates(self.batter, self.pitcher, "S", "R")
        self.assertEqual(rates["hitter_rates"], self.batter.hitter_rates_vs_rhp)
        self.assertEqual(rates["pitcher_rates"], self.pitcher.pitcher_rates_vs_lhh)

    def test_unknown_hands_use_the_overall_card(self):
        rates = cards.plate_appearance_rates(self.batter, self.pitcher, None, None)
        self.assertEqual(rates["hitter_rates"], self.batter.hitter_rates)
        self.assertEqual(rates["pitcher_rates"], self.pitcher.pitcher_rates)

    def test_card_without_splits_uses_the_overall_card(self):
        batter = models.Card(hitter_rates=self.batter.hitter_rates)
        pitcher = models.Card(pitcher_rates=self.pitcher.pitcher_rates)
        rates = cards.plate_appearance_rates(batter, pitcher, "L", "R")
        self.assertEqual(rates["hitter_rates"], batter.hitter_rates)
        self.assertEqual(rates["pitcher_rates"], pitcher.pitcher_rates)


class PlateAppearanceRatesEngineTestCase(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.engine = EngineProcess(build_engine()).start()
        cls.addClassCleanup(cls.engine.stop)
        overridden = override_settings(ENGINE_URL=cls.engine.url)
        overridden.enable()
        cls.addClassCleanup(overridden.disable)

    def matchup_with(self, rates):
        with open(FIXTURE_PATH) as f:
            state = engine_client.start(json.load(f), seed=1)
        batting = state["away"]
        batting["lineup"][batting["batter_index"]]["rates"] = rates["hitter_rates"]
        fielding = state["home"]
        for pitcher in fielding["pitchers"]:
            if pitcher["id"] == fielding["pitcher_slot"]:
                pitcher["rates"] = rates["pitcher_rates"]
        return engine_client.matchup(state)

    def test_engine_matchup_accepts_the_step_rates(self):
        batter, pitcher = platoon_cards()
        vs_lefty = self.matchup_with(cards.plate_appearance_rates(batter, pitcher, "R", "L"))
        vs_righty = self.matchup_with(cards.plate_appearance_rates(batter, pitcher, "L", "R"))
        self.assertAlmostEqual(sum(vs_lefty["probabilities"].values()), 1.0, places=9)
        self.assertAlmostEqual(sum(vs_righty["probabilities"].values()), 1.0, places=9)
        # The right-handed bat strikes out more against a lefty than the left-handed bat does against a righty.
        self.assertGreater(vs_lefty["probabilities"]["k"], vs_righty["probabilities"]["k"])


class SplitsRequestTestCase(SimpleTestCase):
    def test_four_splits_with_splits_tool_ids(self):
        self.assertEqual(
            live_download_fg_splits.SPLITS,
            {
                "bat_vs_lhp": ("B", 1),
                "bat_vs_rhp": ("B", 2),
                "pit_vs_lhh": ("P", 5),
                "pit_vs_rhh": ("P", 6),
            },
        )

    def test_payload_for_one_season_and_split(self):
        payload = live_download_fg_splits.splits_payload(2025, "P", 5)
        self.assertEqual(payload["strPlayerId"], "all")
        self.assertEqual(payload["strSplitArr"], [5])
        self.assertEqual(payload["strPosition"], "P")
        self.assertEqual(payload["strType"], "1")
        self.assertEqual(payload["strStatType"], "player")
        self.assertEqual(payload["strGroup"], "season")
        self.assertEqual(payload["strStartDate"], "2025-01-01")
        self.assertEqual(payload["strEndDate"], "2025-12-31")

    def test_rows_from_column_and_value_arrays(self):
        response = {"k": ["playerid", "playerName", "PA"], "v": [[990001, "Utility Infielder", 150], [990003, "Other", 12]]}
        self.assertEqual(
            live_download_fg_splits.rows_from_response(response),
            [
                {"playerid": 990001, "playerName": "Utility Infielder", "PA": 150},
                {"playerid": 990003, "playerName": "Other", "PA": 12},
            ],
        )

    def test_rows_from_data_list(self):
        rows = [{"playerid": 990001, "PA": 150}]
        self.assertEqual(live_download_fg_splits.rows_from_response({"data": rows}), rows)

    def test_unknown_response_shape_fails_loudly(self):
        with self.assertRaises(CommandError) as caught:
            live_download_fg_splits.rows_from_response({"error": "nope"})
        self.assertIn("error", str(caught.exception))


class _EchoHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        body = self.rfile.read(int(self.headers["Content-Length"]))
        reply = json.dumps({
            "user_agent": self.headers.get("User-Agent"),
            "content_type": self.headers.get("Content-Type"),
            "body": json.loads(body),
        }).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(reply)

    def log_message(self, *args):
        pass


class FgPostTestCase(SimpleTestCase):
    def test_posts_json_with_the_fangraphs_user_agent(self):
        server = HTTPServer(("127.0.0.1", 0), _EchoHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            url = f"http://127.0.0.1:{server.server_port}/api/leaders/splits/splits-leaders"
            echoed = utils.fg_post(url, json={"strSplitArr": [1]}, timeout=5).json()
        finally:
            server.shutdown()
            server.server_close()
        self.assertEqual(echoed["user_agent"], utils.fg_user_agent())
        self.assertEqual(echoed["content_type"], "application/json")
        self.assertEqual(echoed["body"], {"strSplitArr": [1]})


class LoadSplitsTestCase(TestCase):
    def setUp(self):
        self.hitter = models.Player.objects.create(name="Utility Infielder", position="IF", fg_id="990001")
        self.pitcher = models.Player.objects.create(name="Starting Pitcher", position="P", fg_id="990002")
        self.hitter_pss = models.PlayerStatSeason.objects.create(
            player=self.hitter, season=2025, classification="1-mlb", hit_stats=processed(FG_HITTER_ROW)
        )
        self.pitcher_pss = models.PlayerStatSeason.objects.create(
            player=self.pitcher, season=2025, classification="1-mlb", pitch_stats=processed(FG_PITCHER_ROW)
        )

    def run_load(self, *args, directory=FIXTURE_SPLITS_DIR):
        out = StringIO()
        call_command("live_update_splits_from_fg_splits", "--season", "2025", "--dir", directory, *args, stdout=out)
        return out.getvalue()

    def test_stores_each_split_with_loader_key_processing(self):
        self.run_load()
        self.hitter_pss.refresh_from_db()
        self.pitcher_pss.refresh_from_db()
        self.assertEqual(sorted(self.hitter_pss.split_stats), ["bat_vs_lhp", "bat_vs_rhp"])
        self.assertEqual(self.hitter_pss.split_stats["bat_vs_lhp"]["pa"], 150)
        self.assertEqual(self.hitter_pss.split_stats["bat_vs_lhp"]["1b"], 25)
        self.assertEqual(self.hitter_pss.split_stats["bat_vs_rhp"]["mlb_org"], "SFG")
        self.assertEqual(sorted(self.pitcher_pss.split_stats), ["pit_vs_lhh", "pit_vs_rhh"])
        self.assertEqual(self.pitcher_pss.split_stats["pit_vs_rhh"]["tbf"], 450)

    def test_reload_replaces_splits(self):
        self.hitter_pss.split_stats = {"bat_vs_lhp": {"pa": 1}, "pit_vs_lhh": {"tbf": 3}}
        self.hitter_pss.save()
        self.run_load()
        self.hitter_pss.refresh_from_db()
        self.assertEqual(self.hitter_pss.split_stats["bat_vs_lhp"]["pa"], 150)
        self.assertNotIn("pit_vs_lhh", self.hitter_pss.split_stats)

    def test_does_not_create_stat_seasons(self):
        before = models.PlayerStatSeason.objects.count()
        output = self.run_load()
        self.assertEqual(models.PlayerStatSeason.objects.count(), before)
        self.assertIn("Updated splits for 2 players", output)

    def test_dry_run_writes_nothing(self):
        output = self.run_load("--dry-run")
        self.hitter_pss.refresh_from_db()
        self.assertIsNone(self.hitter_pss.split_stats)
        self.assertIn("DRY RUN", output)

    def test_rows_without_counting_columns_fail_loudly(self):
        scratch = os.path.join(os.path.dirname(FIXTURE_SPLITS_DIR), "_splits_missing_columns")
        os.makedirs(scratch, exist_ok=True)
        try:
            for key in live_download_fg_splits.SPLITS:
                with open(os.path.join(FIXTURE_SPLITS_DIR, f"fg_mlb_splits_{key}.json")) as f:
                    rows = json.load(f)
                if key == "bat_vs_lhp":
                    rows = [{k: v for k, v in row.items() if k != "1B"} for row in rows]
                with open(os.path.join(scratch, f"fg_mlb_splits_{key}.json"), "w") as f:
                    json.dump(rows, f)
            with self.assertRaises(CommandError) as caught:
                self.run_load(directory=scratch)
        finally:
            for name in os.listdir(scratch):
                os.remove(os.path.join(scratch, name))
            os.rmdir(scratch)
        self.assertIn("bat_vs_lhp", str(caught.exception))
        self.assertIn("1B", str(caught.exception))
        self.hitter_pss.refresh_from_db()
        self.assertIsNone(self.hitter_pss.split_stats)


@override_settings(CURRENT_SEASON=2026, CURRENT_SEASON_TYPE="midseason")
class GenerateSplitCardsTestCase(TestCase):
    def setUp(self):
        self.hitter = models.Player.objects.create(name="Utility Infielder", position="IF", fg_id="990001", bats="S")
        self.pitcher = models.Player.objects.create(name="Starting Pitcher", position="P", fg_id="990002", throws="L")
        self.hitter_pss = models.PlayerStatSeason.objects.create(
            player=self.hitter, season=2025, classification="1-mlb", hit_stats=processed(FG_HITTER_ROW)
        )
        models.PlayerStatSeason.objects.create(
            player=self.pitcher, season=2025, classification="1-mlb", pitch_stats=processed(FG_PITCHER_ROW)
        )
        call_command("live_update_splits_from_fg_splits", "--season", "2025", "--dir", FIXTURE_SPLITS_DIR, stdout=StringIO())
        self.hitter_pss.refresh_from_db()

    def generate(self):
        call_command("generate_cards", "--season", "2025", stdout=StringIO())

    def test_hitter_card_carries_regressed_splits(self):
        self.generate()
        card = models.Card.objects.get(player=self.hitter, season=2025)
        self.assertEqual(card.plate_appearances_vs_lhp, 150)
        self.assertEqual(card.plate_appearances_vs_rhp, 450)
        self.assertAlmostEqual(card.hitter_rates_vs_lhp["k"], (40 + 400 * 0.2) / 550)
        self.assertAlmostEqual(card.hitter_rates_vs_rhp["k"], (80 + 400 * 0.2) / 850)
        self.assertAlmostEqual(sum(card.hitter_rates_vs_lhp.values()), 1.0)
        self.assertAlmostEqual(sum(card.hitter_rates_vs_rhp.values()), 1.0)
        self.assertIsNone(card.pitcher_rates_vs_lhh)

    def test_pitcher_card_carries_regressed_splits(self):
        self.generate()
        card = models.Card.objects.get(player=self.pitcher, season=2025)
        self.assertEqual(card.batters_faced_vs_lhh, 350)
        self.assertEqual(card.batters_faced_vs_rhh, 450)
        self.assertAlmostEqual(card.pitcher_rates_vs_lhh["k"], (80 + 400 * 0.25) / 750)
        self.assertAlmostEqual(card.pitcher_rates_vs_rhh["k"], (120 + 400 * 0.25) / 850)
        self.assertIsNone(card.hitter_rates_vs_lhp)

    def test_missing_split_is_the_overall_card(self):
        self.hitter_pss.split_stats = {"bat_vs_rhp": self.hitter_pss.split_stats["bat_vs_rhp"]}
        self.hitter_pss.save()
        self.generate()
        card = models.Card.objects.get(player=self.hitter, season=2025)
        self.assertEqual(card.hitter_rates_vs_lhp, card.hitter_rates)
        self.assertEqual(card.plate_appearances_vs_lhp, 0)

    def test_regenerating_regenerates_the_splits(self):
        self.generate()
        splits = dict(self.hitter_pss.split_stats)
        splits["bat_vs_lhp"] = dict(splits["bat_vs_lhp"], so=10)
        self.hitter_pss.split_stats = splits
        self.hitter_pss.save()
        self.generate()
        cards_for_player = models.Card.objects.filter(player=self.hitter, season=2025)
        self.assertEqual(cards_for_player.count(), 1)
        self.assertAlmostEqual(cards_for_player.get().hitter_rates_vs_lhp["k"], (10 + 400 * 0.2) / 550)

    def test_generated_cards_feed_a_switch_hitter_step(self):
        self.generate()
        batter = models.Card.objects.get(player=self.hitter, season=2025)
        pitcher = models.Card.objects.get(player=self.pitcher, season=2025)
        rates = cards.plate_appearance_rates(batter, pitcher, self.hitter.bats, self.pitcher.throws)
        self.assertEqual(rates["hitter_rates"], batter.hitter_rates_vs_lhp)
        self.assertEqual(rates["pitcher_rates"], pitcher.pitcher_rates_vs_rhh)


@override_settings(CURRENT_SEASON=2026, CURRENT_SEASON_TYPE="midseason")
class SplitCardDisplayTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        user = User.objects.create_user(username="mgr", password="secret")
        owner = models.Owner.objects.create(user=user, name="Manager")
        models.Team.objects.create(city="Test City", abbreviation="TST", nickname="Testers", owner_obj=owner)
        self.client.login(username="mgr", password="secret")
        self.hitter = models.Player.objects.create(name="Utility Infielder", position="IF", fg_id="990001")
        self.pitcher = models.Player.objects.create(name="Starting Pitcher", position="P", fg_id="990002")
        models.PlayerStatSeason.objects.create(
            player=self.hitter, season=2025, classification="1-mlb", hit_stats=processed(FG_HITTER_ROW)
        )
        models.PlayerStatSeason.objects.create(
            player=self.pitcher, season=2025, classification="1-mlb", pitch_stats=processed(FG_PITCHER_ROW)
        )
        call_command("live_update_splits_from_fg_splits", "--season", "2025", "--dir", FIXTURE_SPLITS_DIR, stdout=StringIO())
        call_command("generate_cards", "--season", "2025", stdout=StringIO())

    def test_hitter_lines_are_overall_then_left_then_right(self):
        card = models.Card.objects.get(player=self.hitter)
        lines = card.hitter_lines()
        self.assertEqual([(label, pa) for label, pa, _ in lines], [("Overall", 600), ("vs LHP", 150), ("vs RHP", 450)])
        self.assertEqual(lines[0][2], card.hitter_line())
        self.assertAlmostEqual(lines[1][2]["k_pct"], card.hitter_rates_vs_lhp["k"])

    def test_pitcher_lines_are_overall_then_left_then_right(self):
        card = models.Card.objects.get(player=self.pitcher)
        lines = card.pitcher_lines()
        self.assertEqual([(label, bf) for label, bf, _ in lines], [("Overall", 800), ("vs LHH", 350), ("vs RHH", 450)])
        self.assertAlmostEqual(lines[2][2]["k_pct"], card.pitcher_rates_vs_rhh["k"])

    def test_player_page_shows_split_lines(self):
        content = self.client.get(f"/players/{self.hitter.id}/").content.decode()
        self.assertIn("vs LHP", content)
        self.assertIn("vs RHP", content)
        card = models.Card.objects.get(player=self.hitter)
        vs_lhp_k = round(card.hitter_rates_vs_lhp["k"] * 100, 1)
        self.assertIn(f"{vs_lhp_k}", content)
        content = self.client.get(f"/players/{self.pitcher.id}/").content.decode()
        self.assertIn("vs LHH", content)
        self.assertIn("vs RHH", content)
