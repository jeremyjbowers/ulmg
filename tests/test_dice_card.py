# ABOUTME: Tests the Strat-style dice card: the 10-by-10 layout of the engine's odds, the d20 splits, and dice that land on the engine's result.
# ABOUTME: Checks the rolls are as fair as rolling first: every chance on the card comes up as often as its outcome's share says.

from collections import Counter

from django.test import SimpleTestCase

from ulmg import dice_card

LEAGUE = {"k": 0.224, "bb": 0.084, "hbp": 0.011, "single": 0.141, "double": 0.043, "triple": 0.0037, "hr": 0.031, "bip_out": 0.4623}


class SlotCountTest(SimpleTestCase):
    def test_the_card_holds_two_thousand_chances_in_the_engines_proportions(self):
        counts = dice_card.slot_counts(LEAGUE)
        self.assertEqual(sum(counts.values()), 2000)
        total = sum(LEAGUE.values())
        for key, p in LEAGUE.items():
            self.assertLessEqual(abs(counts[key] / 2000 - p / total), 1 / 2000, key)

    def test_a_rare_outcome_the_engine_can_draw_still_gets_a_chance(self):
        rare = dict(LEAGUE, triple=0.00001, bip_out=LEAGUE["bip_out"] + LEAGUE["triple"] - 0.00001)
        counts = dice_card.slot_counts(rare)
        self.assertEqual(counts["triple"], 1)
        self.assertEqual(sum(counts.values()), 2000)

    def test_an_outcome_the_engine_cannot_draw_gets_none(self):
        counts = dice_card.slot_counts(dict(LEAGUE, hbp=0.0, bip_out=LEAGUE["bip_out"] + LEAGUE["hbp"]))
        self.assertEqual(counts["hbp"], 0)


class LayoutTest(SimpleTestCase):
    def test_ten_columns_of_ten_cells_run_in_the_engines_order(self):
        card = dice_card.card(LEAGUE)
        self.assertEqual(len(card["columns"]), 10)
        self.assertTrue(all(len(column["cells"]) == 10 for column in card["columns"]))
        self.assertEqual(card["columns"][0]["cells"][0]["parts"][0]["label"], "strikeout")
        self.assertEqual(card["columns"][9]["cells"][9]["parts"][-1]["label"], "out")
        self.assertEqual(len(card["rows"]), 10)
        self.assertIs(card["rows"][3]["cells"][7], card["columns"][7]["cells"][3])

    def test_a_cell_two_outcomes_share_is_split_on_the_d20(self):
        counts = {"k": 450, "bb": 170, "hbp": 20, "single": 287, "double": 86, "triple": 7, "hr": 60, "bip_out": 920}
        card = dice_card.card({key: value / 2000 for key, value in counts.items()})
        cell = card["columns"][2]["cells"][2]  # chances 440 to 459: ten strikeouts, then ten walks
        self.assertTrue(cell["split"])
        self.assertEqual([(p["short"], p["lo"], p["hi"]) for p in cell["parts"]], [("K", 1, 10), ("BB", 11, 20)])
        self.assertFalse(card["columns"][0]["cells"][0]["split"])

    def test_the_odds_line_adds_to_one_hundred(self):
        odds = dice_card.card(LEAGUE)["odds"]
        self.assertAlmostEqual(sum(line["pct"] for line in odds), 100.0)
        self.assertEqual([line["short"] for line in odds], ["K", "BB", "HBP", "1B", "2B", "3B", "HR", "out"])


class DiceTest(SimpleTestCase):
    def test_the_dice_read_a_cell_holding_the_result(self):
        for seed in range(300):
            for key in ("k", "bb", "single", "triple", "hr", "bip_out"):
                card = dice_card.card(LEAGUE, key, seed)
                dice = card["dice"]
                cell = card["columns"][dice["column"] - 1]["cells"][dice["row"] - 1]
                self.assertTrue(cell["hit"])
                lit = [p for p in cell["parts"] if p["hit"]]
                self.assertEqual(len(lit), 1)
                self.assertEqual(lit[0]["key"], key)
                self.assertTrue(lit[0]["lo"] <= dice["d20"] <= lit[0]["hi"])
                self.assertEqual(dice["split"], cell["split"])

    def test_the_same_plate_appearance_always_shows_the_same_roll(self):
        self.assertEqual(dice_card.card(LEAGUE, "single", 99)["dice"], dice_card.card(LEAGUE, "single", 99)["dice"])

    def test_dice_dont_lean_toward_any_chance_of_the_result(self):
        counts = dice_card.slot_counts(LEAGUE)
        seen = Counter(dice_card.pick_slot(counts, "double", seed) for seed in range(counts["double"] * 400))
        first = counts["k"] + counts["bb"] + counts["hbp"] + counts["single"]
        self.assertEqual(set(seen), set(range(first, first + counts["double"])))
        expected = 400
        chi2 = sum((n - expected) ** 2 / expected for n in seen.values())
        # 85 cells, 84 degrees of freedom: the 99.9th percentile is about 129.
        self.assertLess(chi2, 129)

    def test_rolling_the_result_then_the_cell_covers_the_card_evenly(self):
        # The engine's draw then the card's pick is the same as rolling the card first.
        import random

        counts = dice_card.slot_counts(LEAGUE)
        keys = list(counts)
        draw = random.Random(7)
        seen = Counter()
        trials = 200_000
        for seed in range(trials):
            key = draw.choices(keys, weights=[counts[k] for k in keys])[0]
            seen[dice_card.pick_slot(counts, key, seed) // 20] += 1
        chi2 = sum((seen[cell] - trials / 100) ** 2 / (trials / 100) for cell in range(100))
        # 100 cells, 99 degrees of freedom: the 99.9th percentile is about 149.
        self.assertLess(chi2, 149)

    def test_column_and_row_dice_come_from_the_chance(self):
        self.assertEqual(dice_card.dice_for(0), {"column": 1, "row": 1, "d20": 1})
        self.assertEqual(dice_card.dice_for(1999), {"column": 10, "row": 10, "d20": 20})
        self.assertEqual(dice_card.dice_for(20 * 37 + 4), {"column": 4, "row": 8, "d20": 5})


class HitAndRunTest(SimpleTestCase):
    def test_it_halves_strikeouts_and_keeps_the_total(self):
        after = dice_card.with_hit_and_run(LEAGUE)
        self.assertAlmostEqual(after["k"], LEAGUE["k"] / 2)
        self.assertAlmostEqual(sum(after.values()), sum(LEAGUE.values()))
        self.assertEqual(after["hr"], LEAGUE["hr"])
        self.assertGreater(after["single"], LEAGUE["single"])
        self.assertGreater(after["bip_out"], LEAGUE["bip_out"])


class LoggedPlateAppearanceTest(SimpleTestCase):
    def payload(self, outcome, **result):
        return {"card": LEAGUE, "result": {"outcome": outcome, "batter_completed": True, **result}}

    def test_every_ball_in_play_out_reads_an_out_in_play_cell(self):
        for outcome in ("ground_out", "fly_out", "line_out", "grounded_into_double_play", "sacrifice_fly", "reached_on_error"):
            self.assertEqual(dice_card.for_plate_appearance(self.payload(outcome), 5)["result"], "out", outcome)

    def test_bunts_intentional_walks_and_old_logs_read_no_card(self):
        for outcome in ("bunt_single", "bunt_out", "bunt_sacrifice", "intentional_walk", "caught_stealing"):
            self.assertIsNone(dice_card.for_plate_appearance(self.payload(outcome), 5), outcome)
        self.assertIsNone(dice_card.for_plate_appearance({"result": {"outcome": "single"}}, 5))

    def test_a_hit_and_run_reads_the_table_the_engine_read(self):
        card = dice_card.for_plate_appearance(self.payload("single", call_note="hit_and_run_succeeded"), 5)
        self.assertTrue(card["hit_and_run"])
        self.assertEqual(card["odds"][0]["chances"], dice_card.slot_counts(dice_card.with_hit_and_run(LEAGUE))["k"])
