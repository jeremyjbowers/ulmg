# ABOUTME: Tests the Strat-style dice card: the 10-by-10 layout of the engine's table, the d20 splits, the engine's roll as dice, and the ballpark's marks.
# ABOUTME: Checks the card always says what the roll drew and that every outcome keeps its share to within one chance in 2,000.

import random

from django.test import SimpleTestCase

from ulmg import dice_card

LEAGUE = {"k": 0.224, "bb": 0.084, "hbp": 0.011, "single": 0.141, "double": 0.043, "triple": 0.0037, "hr": 0.031, "bip_out": 0.4623}
# The same matchup in a park that only takes away home runs.
NEUTRAL = dict(LEAGUE, hr=0.026, bip_out=LEAGUE["bip_out"] + 0.005)
PARK = {"id": "yard", "run_factor": 1.04, "single_factor": None, "double_factor": 0.97, "triple_factor": None, "hr_factor": 1.19}


def engine_result(roll, probabilities=LEAGUE, neutral=NEUTRAL, outcome="single", **extra):
    return {
        "outcome": outcome,
        "batter_completed": True,
        "dice": {"roll": roll, "probabilities": probabilities, "neutral_park": neutral, "park": PARK},
        **extra,
    }


class BoundaryTest(SimpleTestCase):
    def test_every_outcome_keeps_its_share_to_within_one_chance(self):
        counts = dice_card.counts_from(dice_card.boundaries(LEAGUE))
        self.assertEqual(sum(counts.values()), 2000)
        total = sum(LEAGUE.values())
        for key, p in LEAGUE.items():
            self.assertLessEqual(abs(counts[key] - p / total * 2000), 1, key)

    def test_the_card_always_reads_what_the_roll_drew(self):
        draw = random.Random(3)
        for _ in range(20_000):
            roll = draw.random()
            card = dice_card.card(LEAGUE, roll)
            drawn = dice_card.read(LEAGUE, roll)
            self.assertEqual(card["result"], dice_card.LABELS[drawn][0], roll)
            counts = {line["key"]: line["chances"] for line in card["odds"]}
            for key, p in LEAGUE.items():
                self.assertLessEqual(abs(counts[key] - p / sum(LEAGUE.values()) * 2000), 2, (roll, key))

    def test_a_roll_on_a_boundary_chance_moves_the_boundary_to_the_drawn_side(self):
        # Strikeouts end at 448 chances. A roll just past 0.224 draws a walk on chance 448.
        roll = 0.224 + 1e-9
        self.assertEqual(dice_card.read(LEAGUE, roll), "bb")
        card = dice_card.card(LEAGUE, roll)
        self.assertEqual(card["result"], "WALK")
        self.assertEqual(card["dice"], {"column": 3, "row": 3, "d20": 9, "split": True, "park": False})

    def test_read_matches_the_engines_running_total(self):
        self.assertEqual(dice_card.read(LEAGUE, 0.0), "k")
        self.assertEqual(dice_card.read(LEAGUE, 0.2239999), "k")
        self.assertEqual(dice_card.read(LEAGUE, 0.224), "bb")
        self.assertEqual(dice_card.read(LEAGUE, 0.9999999), "bip_out")


class LayoutTest(SimpleTestCase):
    def test_ten_columns_of_ten_cells_run_in_the_engines_order(self):
        card = dice_card.card(LEAGUE)
        self.assertEqual(len(card["columns"]), 10)
        self.assertTrue(all(len(column["cells"]) == 10 for column in card["columns"]))
        self.assertEqual(card["columns"][0]["cells"][0]["parts"][0]["label"], "strikeout")
        self.assertEqual(card["columns"][9]["cells"][9]["parts"][-1]["label"], "out")
        self.assertIs(card["rows"][3]["cells"][7], card["columns"][7]["cells"][3])

    def test_a_cell_two_outcomes_share_is_split_on_the_d20(self):
        counts = {"k": 450, "bb": 170, "hbp": 20, "single": 287, "double": 86, "triple": 7, "hr": 60, "bip_out": 920}
        card = dice_card.card({key: value / 2000 for key, value in counts.items()})
        cell = card["columns"][2]["cells"][2]  # chances 440 to 459: ten strikeouts, then ten walks
        self.assertTrue(cell["split"])
        self.assertEqual([(p["short"], p["lo"], p["hi"]) for p in cell["parts"]], [("K", 1, 10), ("BB", 11, 20)])

    def test_the_dice_light_one_part_of_one_cell(self):
        card = dice_card.card(LEAGUE, 0.5)
        lit = [(c["number"], cell["row"], p["key"]) for c in card["columns"] for cell in c["cells"] for p in cell["parts"] if p["hit"]]
        self.assertEqual(lit, [(6, 1, "double")])

    def test_column_and_row_dice_come_from_the_chance(self):
        self.assertEqual(dice_card.dice_for(0), {"column": 1, "row": 1, "d20": 1})
        self.assertEqual(dice_card.dice_for(1999), {"column": 10, "row": 10, "d20": 20})
        self.assertEqual(dice_card.dice_for(20 * 37 + 4), {"column": 4, "row": 8, "d20": 5})
        self.assertEqual(dice_card.slot_of(0.9999999999), 1999)


class BallparkTest(SimpleTestCase):
    def test_chances_the_park_adds_are_marked_at_the_end_of_their_run(self):
        card = dice_card.card(LEAGUE, None, NEUTRAL)
        hr = next(line for line in card["odds"] if line["key"] == "hr")
        self.assertEqual(hr["park"], 10)
        self.assertAlmostEqual(hr["park_pct"], 0.5)
        out = next(line for line in card["odds"] if line["key"] == "bip_out")
        self.assertEqual(out["park"], -10)
        marked = [p for c in card["columns"] for cell in c["cells"] for p in cell["parts"] if p["park"]]
        self.assertEqual(sum(p["hi"] - p["lo"] + 1 for p in marked), 10)
        self.assertEqual({p["key"] for p in marked}, {"hr"})

    def test_a_roll_on_a_park_chance_says_so(self):
        # Home runs run from chance 1,013 to 1,074; the park's ten are the last ten.
        self.assertTrue(dice_card.card(LEAGUE, 1070 / 2000, NEUTRAL)["dice"]["park"])
        self.assertFalse(dice_card.card(LEAGUE, 1020 / 2000, NEUTRAL)["dice"]["park"])

    def test_a_neutral_park_marks_nothing(self):
        card = dice_card.card(LEAGUE, 0.3, LEAGUE)
        self.assertFalse(any(line["park"] for line in card["odds"]))

    def test_park_factors_fall_back_to_the_run_factor(self):
        self.assertEqual(dice_card.park_factors(PARK), {"single": 1.04, "double": 0.97, "triple": 1.04, "hr": 1.19})


class LoggedPlateAppearanceTest(SimpleTestCase):
    def test_the_card_comes_from_the_engines_dice(self):
        card = dice_card.for_plate_appearance(engine_result(0.40))
        self.assertEqual(card["result"], "SINGLE")
        self.assertEqual([(f["short"], f["tone"]) for f in card["park"]["factors"]], [("1B", "up"), ("2B", "down"), ("3B", "up"), ("HR", "up")])
        self.assertEqual([line["key"] for line in card["park"]["moved"]], ["hr", "bip_out"])
        self.assertFalse(card["hit_and_run"])

    def test_a_hit_and_run_is_tagged(self):
        self.assertTrue(dice_card.for_plate_appearance(engine_result(0.40, call_note="hit_and_run_succeeded"))["hit_and_run"])

    def test_no_dice_means_no_card(self):
        self.assertIsNone(dice_card.for_plate_appearance({"outcome": "bunt_out", "batter_completed": True}))
        self.assertIsNone(dice_card.for_plate_appearance(None))
