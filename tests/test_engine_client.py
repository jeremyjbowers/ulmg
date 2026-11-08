# ABOUTME: Tests the engine client against a real engine process that the tests build and start.
# ABOUTME: Covers start, two steps in a row, replay, determinism, calls, card batted balls, matchup, and a down engine.
import json

from django.test import SimpleTestCase, override_settings

from tests.engine_process import (
    FIXTURE_PATH,
    EngineProcess,
    EngineToolMissing,
    build_engine,
    find_cargo,
)
from tests.test_cards import (
    FG_HITTER_ROW,
    FG_PITCHER_ROW,
    HITTER_BATTED_BALLS,
    PITCHER_BATTED_BALLS,
    processed,
)
from ulmg import cards, engine_client


def load_fixture():
    with open(FIXTURE_PATH) as handle:
        return json.load(handle)


class CargoRequirementTestCase(SimpleTestCase):
    def test_missing_cargo_fails_with_a_message_naming_cargo(self):
        with self.assertRaises(EngineToolMissing) as caught:
            find_cargo(path="/nonexistent")
        self.assertIn("cargo is not installed", str(caught.exception))


class EngineClientTestCase(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.binary = build_engine()
        cls.engine = EngineProcess(cls.binary).start()
        cls.addClassCleanup(cls.engine.stop)
        overridden = override_settings(ENGINE_URL=cls.engine.url)
        overridden.enable()
        cls.addClassCleanup(overridden.disable)

    def opening_state(self, seed=1):
        return engine_client.start(load_fixture(), seed=seed)

    def test_health(self):
        self.assertEqual(engine_client.health(), {"status": "ok"})

    def test_start_returns_the_opening_state(self):
        state = self.opening_state()
        self.assertEqual(state["inning"], 1)
        self.assertEqual(state["outs"], 0)
        self.assertEqual(state["results"], [])
        self.assertEqual(state["status"], "in_progress")

    def test_the_second_step_follows_the_first(self):
        first = engine_client.step(self.opening_state(), seed=11)
        self.assertEqual(len(first["state"]["results"]), 1)
        self.assertEqual(first["state"]["results"][0], first["result"])

        second = engine_client.step(first["state"], seed=12)
        results = second["state"]["results"]
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0], first["result"], "the first plate appearance changed")
        self.assertEqual(results[1], second["result"])
        self.assertNotEqual(
            results[1]["batter_id"],
            results[0]["batter_id"],
            "the second step did not advance the batting order",
        )

    def test_a_fresh_engine_process_continues_from_the_returned_state(self):
        first = engine_client.step(self.opening_state(), seed=21)
        here = engine_client.step(first["state"], seed=22)

        fresh = EngineProcess(self.binary).start()
        try:
            with self.settings(ENGINE_URL=fresh.url):
                there = engine_client.step(first["state"], seed=22)
        finally:
            fresh.stop()

        self.assertEqual(there, here)
        self.assertEqual(len(there["state"]["results"]), 2)

    def test_the_same_state_call_and_seed_give_the_same_result(self):
        state = self.opening_state(seed=3)
        for call in [None, "bunt", "intentional_walk", "steal", "hit_and_run", "infield_in"]:
            with self.subTest(call=call):
                one = engine_client.step(state, seed=99, call=call)
                two = engine_client.step(state, seed=99, call=call)
                self.assertEqual(one, two)

    def test_the_seed_reaches_the_draw(self):
        state = self.opening_state(seed=3)
        results = {
            json.dumps(engine_client.step(state, seed=seed)["result"], sort_keys=True)
            for seed in range(20)
        }
        self.assertGreater(len(results), 1)

    def test_an_intentional_walk_call_is_honored(self):
        stepped = engine_client.step(self.opening_state(), seed=4, call="intentional_walk")
        self.assertEqual(stepped["result"]["outcome"], "intentional_walk")

    def test_matchup_reports_probabilities_without_drawing(self):
        state = self.opening_state(seed=8)
        matchup = engine_client.matchup(state)
        self.assertEqual(matchup["batter_id"], state["away"]["lineup"][0]["id"])
        self.assertEqual(matchup["pitcher_id"], state["home"]["pitcher_slot"])
        self.assertAlmostEqual(sum(matchup["probabilities"].values()), 1.0, places=9)
        self.assertEqual(engine_client.matchup(state), matchup)

    def test_an_infield_in_call_holds_the_runner_on_third(self):
        state = self.opening_state(seed=2)
        runner = state["away"]["lineup"][8]["id"]
        state["bases"]["third"] = runner
        ground_outs = 0
        for seed in range(200):
            stepped = engine_client.step(state, seed=seed, call="infield_in")
            if stepped["result"]["outcome"] == "ground_out":
                ground_outs += 1
                self.assertEqual(stepped["result"]["change"]["runs_scored"], 0)
                self.assertEqual(stepped["state"]["bases"]["third"], runner)
        self.assertGreater(ground_outs, 0)

    def test_cards_batted_ball_rates_are_accepted_by_the_engine(self):
        fixture = load_fixture()
        hitter_rates = cards.batted_ball_rates(processed(FG_HITTER_ROW, **HITTER_BATTED_BALLS))
        pitcher_rates = cards.batted_ball_rates(processed(FG_PITCHER_ROW, **PITCHER_BATTED_BALLS))
        for team in ("away", "home"):
            for batter in fixture[team]["lineup"]:
                batter["batted_balls"] = hitter_rates
            for pitcher in fixture[team]["pitchers"]:
                pitcher["batted_balls"] = pitcher_rates
        state = engine_client.start(fixture, seed=1)
        self.assertEqual(state["away"]["lineup"][0]["batted_balls"], hitter_rates)
        self.assertEqual(state["home"]["pitchers"][0]["batted_balls"], pitcher_rates)
        stepped = engine_client.step(state, seed=5)
        self.assertEqual(len(stepped["state"]["results"]), 1)

    def test_a_rejected_call_raises_the_engine_message(self):
        with self.assertRaises(engine_client.EngineError) as caught:
            engine_client.step(self.opening_state(), seed=4, call="squeeze")
        self.assertNotIsInstance(caught.exception, engine_client.EngineUnavailable)
        self.assertEqual(caught.exception.status, 400)
        self.assertIn("intentional_walk", str(caught.exception))


class EngineDownTestCase(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.binary = build_engine()

    def test_a_stopped_engine_raises_engine_unavailable(self):
        engine = EngineProcess(self.binary).start()
        with self.settings(ENGINE_URL=engine.url):
            state = engine_client.start(load_fixture(), seed=1)
            engine.stop()
            with self.assertRaises(engine_client.EngineUnavailable) as caught:
                engine_client.step(state, seed=1)
        self.assertIn(engine.url, str(caught.exception))

    def test_an_unset_engine_url_raises_engine_unavailable(self):
        with self.settings(ENGINE_URL=None):
            with self.assertRaises(engine_client.EngineUnavailable) as caught:
                engine_client.health()
        self.assertIn("ENGINE_URL", str(caught.exception))
