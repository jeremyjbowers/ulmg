# ABOUTME: Tests the top-down field: the park drawn from its dimensions, rating and speed labels, and the last play's moves.
# ABOUTME: The geometry tests are plain functions; the move tests use engine-shaped plate appearance results.

from django.test import SimpleTestCase

from ulmg import game_field, park


def _result(outcome, batter, after, scored=(), runs=0, outs=0):
    return {
        "outcome": outcome,
        "batter_id": batter,
        "count": {"balls": 1, "strikes": 1},
        "change": {"outs_added": outs, "runs_scored": runs, "bases": after},
        "baserunning": [{"Scored": {"runner": runner}} for runner in scored],
    }


class GeometryTest(SimpleTestCase):
    def test_the_infield_is_enlarged_and_the_outfield_compressed(self):
        self.assertAlmostEqual(game_field.warp(90), 153.0)
        self.assertAlmostEqual(game_field.warp(130), 221.0)
        self.assertAlmostEqual(game_field.warp(400), 221.0 + 270 * 0.72)

    def test_center_field_is_straight_up_and_first_base_is_to_the_right(self):
        x, y = game_field.point(400, 0)
        self.assertEqual(x, game_field.HOME[0])
        self.assertLess(y, game_field.HOME[1])
        first = game_field.base_spots()["first"]
        third = game_field.base_spots()["third"]
        self.assertGreater(first[0], game_field.HOME[0])
        self.assertLess(third[0], game_field.HOME[0])
        self.assertEqual(first[1], third[1])

    def test_a_world_landing_in_feet_maps_onto_the_same_drawing(self):
        self.assertEqual(game_field.world_point(0, 300), game_field.point(300, 0))
        x, _ = game_field.world_point(-120, 270)
        self.assertLess(x, game_field.HOME[0], "a ball to left lands left of home")


class ParkDrawingTest(SimpleTestCase):
    def test_the_generic_park_has_no_tall_wall_and_labels_its_distances(self):
        drawing = game_field.park_drawing(park.clean_rules({}))
        self.assertEqual(drawing["tall_walls"], [])
        self.assertEqual([label["text"] for label in drawing["labels"]], ["330", "380", "400", "380", "330"])
        self.assertFalse(drawing["turf"])

    def test_fenway_marks_its_wall_in_left_and_draws_the_short_lines(self):
        fenway = park.dimension_file()["3"]
        drawing = game_field.park_drawing(park.clean_rules(fenway))
        # The Monster from the line to left-center, then on to center (17 feet), then center to right-center.
        self.assertEqual(len(drawing["tall_walls"]), 3)
        texts = [label["text"] for label in drawing["labels"]]
        self.assertEqual(texts[0], "310 · 37′ wall")
        self.assertEqual(texts[-1], "302")
        generic = game_field.park_drawing(park.clean_rules({}))
        self.assertNotEqual(drawing["fence"], generic["fence"], "the fence follows the park's own distances")

    def test_a_turf_park_says_so(self):
        drawing = game_field.park_drawing(park.clean_rules({"surface": "turf", "roof": "dome"}))
        self.assertTrue(drawing["turf"])


class LabelTest(SimpleTestCase):
    def test_ratings_are_the_engine_rating_times_ten_with_a_real_minus(self):
        self.assertEqual(game_field.rating_runs(0.38), 3.8)
        self.assertEqual(game_field.rating_label(3.8), "+3.8")
        self.assertEqual(game_field.rating_label(-2.0), "−2.0")
        self.assertEqual(game_field.rating_label(0.0), "0.0")
        self.assertEqual(game_field.rating_runs(-0.0), 0.0)


class BallTrackTest(SimpleTestCase):
    def test_an_error_lands_as_a_ground_ball_and_says_error(self):
        shown = game_field.ball_track({"outcome": "reached_on_error", "batter_id": "4", "count": {"balls": 1, "strikes": 1}})
        self.assertEqual(shown["label"], "ERROR")
        self.assertEqual(shown["kind"], "ground")

    def test_a_single_is_a_line_drive_that_lands_on_a_single_spot(self):
        ball = game_field.ball_track({"outcome": "single", "batter_id": "9", "count": {"balls": 1, "strikes": 2}})
        self.assertEqual(ball["kind"], "line")
        self.assertIn((ball["x"], ball["z"]), game_field.LANDINGS["single"])

    def test_the_same_batted_ball_lands_in_the_same_place(self):
        result = {"outcome": "line_out", "batter_id": "4", "count": {"balls": 0, "strikes": 1}}
        self.assertEqual(game_field.ball_track(result), game_field.ball_track(result))

    def test_a_strikeout_has_no_landing(self):
        self.assertIsNone(game_field.ball_track({"outcome": "strikeout", "batter_id": "1", "count": {"balls": 0, "strikes": 3}}))
        self.assertEqual(game_field.banner_label("strikeout"), "STRIKEOUT")


class LogTextTest(SimpleTestCase):
    def test_the_half_inning_and_count_come_off_the_front_of_a_log_line(self):
        self.assertEqual(game_field.split_log_text("Top 3, 2-1: Reyes singled. 4 pitches."), ("2-1", "Reyes singled. 4 pitches."))
        self.assertEqual(game_field.split_log_text("Reyes singled."), ("", "Reyes singled."))


class RunnerMoveTest(SimpleTestCase):
    def test_a_single_moves_the_batter_to_first_and_the_runner_up(self):
        result = _result("single", "9", {"first": "9", "second": None, "third": "4"})
        moves = game_field.runner_moves({"first": "4", "second": None, "third": None}, result)
        self.assertEqual(moves, [("4", "first", "third"), ("9", "home", "first")])

    def test_a_runner_who_scores_goes_home_and_a_runner_put_out_is_out(self):
        result = _result("sacrifice_fly", "9", {"first": None, "second": None, "third": None}, scored=["5"], runs=1, outs=1)
        moves = game_field.runner_moves({"first": None, "second": None, "third": "5"}, result)
        self.assertEqual(moves, [("5", "third", "home")])
        result = _result("grounded_into_double_play", "9", {"first": None, "second": None, "third": None}, outs=2)
        moves = game_field.runner_moves({"first": "4", "second": None, "third": None}, result)
        self.assertEqual(moves, [("4", "first", "out")])

    def test_a_home_run_takes_the_batter_all_the_way_around(self):
        result = _result("home_run", "9", {"first": None, "second": None, "third": None}, scored=["4", "9"], runs=2)
        moves = game_field.runner_moves({"first": "4", "second": None, "third": None}, result)
        self.assertEqual(moves, [("4", "first", "home"), ("9", "home", "home")])
