# ABOUTME: Tests the top-down field: the park drawn from its dimensions, rating and speed labels, and the last play's moves.
# ABOUTME: The geometry tests are plain functions; the move tests use engine-shaped plate appearance results.

import math

from django.template.loader import render_to_string
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


def _points(svg_points):
    return [tuple(float(n) for n in pair.split(",")) for pair in svg_points.split()]


def _distance_to_line(spot, a, b):
    """How far a spot is from the line through a and b, in SVG units."""
    (x, y), (ax, ay), (bx, by) = spot, a, b
    return abs((bx - ax) * (ay - y) - (ax - x) * (by - ay)) / ((bx - ax) ** 2 + (by - ay) ** 2) ** 0.5


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


    def test_the_diamond_is_square_and_the_mound_sits_at_its_center(self):
        bases = game_field.base_spots()
        home, first, second, third = (bases[b] for b in ("home", "first", "second", "third"))
        sides = [math.dist(home, first), math.dist(first, second), math.dist(second, third), math.dist(third, home)]
        for side in sides:
            self.assertAlmostEqual(side, sides[0], delta=0.2)
        mound = game_field.mound_spot()
        self.assertAlmostEqual(math.dist(mound, home), math.dist(mound, second), delta=0.2)
        self.assertAlmostEqual(math.dist(mound, first), math.dist(mound, third), delta=0.2)
        self.assertAlmostEqual(math.dist(mound, home), math.dist(mound, first), delta=0.2)

    def test_the_drawing_and_the_pitch_both_start_from_the_mound(self):
        drawing = game_field.park_drawing(park.clean_rules({}))
        self.assertEqual(drawing["mound"], game_field.mound_spot())
        self.assertEqual(game_field.ball_path(None)[0], game_field.mound_spot())

    def test_the_pitcher_stands_on_the_mound(self):
        pitcher = game_field._fielder("P", None, None)
        self.assertEqual((pitcher["x"], pitcher["y"]), game_field.mound_spot())


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

    def test_a_traced_fence_is_drawn_straight_through_each_of_its_points(self):
        traced = [[-45, 310], [-30, 318], [-20, 379], [0, 390], [10, 420], [22.5, 380], [40, 380], [45, 302]]
        drawing = game_field.park_drawing(park.clean_rules({"fence_ft": traced}))
        self.assertNotIn("Q", drawing["fence"], "a traced wall has corners, not curves")
        for degrees, feet in traced:
            x, y = game_field.point(feet, degrees)
            self.assertIn(f"L {x} {y}", drawing["fence"])
        self.assertEqual(drawing["foul_lines"], [game_field.point(310, -45), game_field.point(302, 45)])

    def test_a_park_without_a_traced_fence_keeps_its_curved_wall(self):
        drawing = game_field.park_drawing(park.clean_rules({}))
        self.assertIn("Q", drawing["fence"])

    def test_distance_labels_sit_inside_the_traced_fence_where_it_was_measured(self):
        traced = [[-45, 310], [-22.5, 379], [-10, 330], [0, 390], [22.5, 380], [45, 302]]
        drawing = game_field.park_drawing(park.clean_rules({"distances_ft": {"center": 390}, "fence_ft": traced}))
        center = drawing["labels"][2]
        self.assertEqual((center["x"], center["y"]), game_field.point(390 - game_field.LABEL_INSET_FT, 0))
        self.assertEqual(center["text"], "390")

    def test_a_tall_wall_follows_the_traced_fence_between_its_measured_points(self):
        traced = [[-45, 310], [-35, 330], [-22.5, 379], [0, 390], [22.5, 380], [45, 302]]
        rules = park.clean_rules({"fence_ft": traced, "wall_ft": {"lf_line": 37, "left_center": 37}})
        drawing = game_field.park_drawing(rules)
        self.assertEqual(len(drawing["tall_walls"]), 2, "line to left-center, then left-center to center")
        monster = drawing["tall_walls"][0]
        for degrees, feet in traced[:3]:
            x, y = game_field.point(feet, degrees)
            self.assertIn(f"{x} {y}", monster)
        self.assertNotIn("Q", monster)

    def test_outfielders_play_off_the_traced_fence(self):
        traced = [[-45, 330], [-27, 300], [0, 400], [27, 400], [45, 330]]
        fence = game_field.fence_points(park.clean_rules({"fence_ft": traced}))
        self.assertEqual(game_field.fence_at(fence, -27), 300)
        self.assertEqual(game_field.fielder_spot("LF", fence), (300 - game_field.OUTFIELD_GAP_FT, -27))
        self.assertEqual(game_field.fielder_spot("RF", fence), (285, 27))

    def test_without_a_traced_fence_the_five_distances_are_the_fence(self):
        fence = game_field.fence_points(park.clean_rules({}))
        self.assertEqual(fence, [(-45.0, 330), (-22.5, 380), (0.0, 400), (22.5, 380), (45.0, 330)])
        self.assertEqual(game_field.fence_at(fence, -11.25), 390)

    def test_a_turf_park_says_so(self):
        drawing = game_field.park_drawing(park.clean_rules({"surface": "turf", "roof": "dome"}))
        self.assertTrue(drawing["turf"])

    def test_grass_and_turf_name_the_colors_the_field_paints(self):
        grass = game_field.park_drawing(park.clean_rules({}))
        turf = game_field.park_drawing(park.clean_rules({"surface": "turf"}))
        self.assertEqual(grass["colors"], game_field.GRASS_COLORS)
        self.assertEqual(turf["colors"], game_field.TURF_COLORS)
        self.assertNotEqual(grass["colors"]["foul"], turf["colors"]["foul"])

    def test_the_infield_grass_runs_parallel_to_each_baseline_so_the_basepaths_are_even(self):
        drawing = game_field.park_drawing(park.clean_rules({}))
        grass = _points(drawing["infield_grass"])
        diamond = _points(drawing["baselines"])
        self.assertEqual(len(grass), 4)
        for side in range(4):
            a, b = diamond[side], diamond[(side + 1) % 4]
            start, end = grass[side], grass[(side + 1) % 4]
            gap_at_start = _distance_to_line(start, a, b)
            gap_at_end = _distance_to_line(end, a, b)
            self.assertAlmostEqual(gap_at_start, game_field.BASEPATH_WIDTH, delta=0.2)
            self.assertAlmostEqual(gap_at_end, game_field.BASEPATH_WIDTH, delta=0.2)


def _field_svg(rules):
    field = {"drawing": game_field.park_drawing(rules), "park": {"name": "Park", "facts": ""}, "fielders": [], "runners": [], "text": ""}
    return render_to_string("includes/game_field.html", {"field": field})


def _pattern(svg, pattern_id):
    start = svg.index(f'<pattern id="{pattern_id}"')
    return svg[start : svg.index("</pattern>", start)]


class GrassAndStandsTest(SimpleTestCase):
    def test_the_infield_grass_is_crosshatched_square_to_the_baselines(self):
        svg = _field_svg(park.clean_rules({}))
        cross = _pattern(svg, "infield-cross")
        self.assertIn('patternTransform="rotate(45)"', cross)
        # A checkerboard: two alternate squares on the diagonal of each cell.
        self.assertEqual(cross.count("infield_alt") + cross.count(game_field.GRASS_COLORS["infield_alt"]), 2)
        self.assertIn('fill="url(#infield-cross)"', svg)

    def test_foul_ground_has_no_mow_lines_only_a_mottle_that_is_the_same_each_time_for_a_park(self):
        generic = park.clean_rules({})
        fenway = park.clean_rules(park.dimension_file()["3"])
        marks = game_field.park_drawing(generic)["foul_marks"]
        self.assertGreater(len(marks), 20)
        self.assertEqual(marks, game_field.park_drawing(generic)["foul_marks"])
        self.assertNotEqual(marks, game_field.park_drawing(fenway)["foul_marks"])
        svg = _field_svg(generic)
        self.assertNotIn('id="foul-mow"', svg)
        self.assertGreaterEqual(_pattern(svg, "foul-mottle").count("<ellipse"), len(marks))

    def test_foul_ground_is_a_band_along_each_line_as_wide_as_the_park_says(self):
        narrow = game_field.foul_band(park.clean_rules({"foul_ft": 30}))
        wide = game_field.foul_band(park.clean_rules({"foul_ft": 70}))
        corners = [game_field.point(330, -45), game_field.point(330, 45)]
        for band, feet in ((narrow, 30), (wide, 70)):
            for outer, corner in ((band["left"], corners[0]), (band["right"], corners[1])):
                # The outer edge of the band at the pole is the band's width from the foul line.
                self.assertAlmostEqual(_distance_to_line(outer, game_field.HOME, corner), feet * game_field.FOUL_SCALE, delta=0.3)
        self.assertIn("Q", narrow["path"], "the band rounds behind home plate")

    def test_the_stands_and_bleachers_change_from_park_to_park_and_not_from_game_to_game(self):
        generic = game_field.park_drawing(park.clean_rules({}))["stands"]
        fenway = game_field.park_drawing(park.clean_rules(park.dimension_file()["3"]))["stands"]
        self.assertEqual(generic, game_field.park_drawing(park.clean_rules({}))["stands"])
        self.assertNotEqual(generic, fenway)
        self.assertGreater(len(generic["grandstand"]), 20)
        self.assertTrue(generic["aisles"])
        self.assertIn(generic["seat"], [seat for seat, _ in game_field.SEAT_COLORS])

    def test_the_seats_ring_the_field_and_the_bleachers_sit_behind_the_outfield_wall(self):
        svg = _field_svg(park.clean_rules({}))
        self.assertIn('id="stand-edge"', svg)
        self.assertIn('clip-path="url(#bleacher-clip)"', svg)
        self.assertIn('class="foul-ground"', svg)


def _ring_widths(bands, color):
    return [band["width"] for band in bands if band["color"] == color]


class StadiumTest(SimpleTestCase):
    def setUp(self):
        self.stands = game_field.park_drawing(park.clean_rules({}))["stands"]

    def test_the_grandstand_has_a_lower_deck_a_concourse_and_an_upper_deck(self):
        bands = self.stands["grandstand"]
        widths = [band["width"] for band in bands]
        self.assertEqual(widths, sorted(widths, reverse=True), "drawn from the back row to the front")
        concourse = _ring_widths(bands, game_field.CONCOURSE)
        self.assertEqual(len(concourse), 1)
        lower_back = 2 * game_field.LOWER_DECK
        self.assertTrue(lower_back < concourse[0] <= lower_back + 2 * game_field.CONCOURSE_WIDTH + 4)
        self.assertTrue(_ring_widths(bands, self.stands["seat"]), "the lower deck is in the park's seat color")
        self.assertTrue(_ring_widths(bands, self.stands["upper"]), "the upper deck is its own shade")
        self.assertNotEqual(self.stands["upper"], self.stands["seat"])
        self.assertTrue(all(w <= lower_back for w in _ring_widths(bands, self.stands["seat"])))
        self.assertTrue(all(w > concourse[0] for w in _ring_widths(bands, self.stands["upper"])))

    def test_the_outfield_bleachers_end_at_a_back_wall_and_the_ground_lies_beyond(self):
        bands = self.stands["bleachers"]
        self.assertEqual(bands[0]["color"], game_field.BACK_WALL)
        self.assertLessEqual(bands[0]["width"], 2 * game_field.BLEACHER_DEPTH + 8)
        self.assertTrue(_ring_widths(bands, self.stands["bleacher"]))
        svg = _field_svg(park.clean_rules({}))
        self.assertIn(f'fill="{game_field.GROUND}"', svg)

    def test_the_bleachers_ring_the_traced_wall(self):
        traced = [[-45, 310], [-20, 379], [0, 420], [30, 380], [45, 302]]
        drawing = game_field.park_drawing(park.clean_rules({"fence_ft": traced}))
        for degrees, feet in traced:
            x, y = game_field.point(feet, degrees)
            self.assertIn(f"L {x} {y}", drawing["stands"]["edge"])

    def test_the_lower_deck_has_tunnels_behind_the_foul_lines(self):
        tunnels = self.stands["tunnels"]
        self.assertGreater(len(tunnels), 6)
        hx, hy = game_field.HOME
        for tunnel in tunnels:
            off_center = math.degrees(math.atan2(tunnel["x"] - hx, hy - tunnel["y"]))
            self.assertGreater(abs(off_center), 45, "a tunnel sits in the grandstand, not the outfield")

    def test_each_team_has_a_dugout_in_foul_ground_clear_of_the_runner_at_first(self):
        drawing = game_field.park_drawing(park.clean_rules({}))
        third, first = drawing["dugouts"]
        hx, hy = game_field.HOME
        self.assertLess(third["x"], hx)
        self.assertGreater(first["x"], hx)
        base_y = game_field.base_spots()["first"][1]
        for dugout in (third, first):
            self.assertGreater(dugout["y"], base_y + 40, "below the runner's name at first or third")
        svg = _field_svg(park.clean_rules({}))
        self.assertEqual(svg.count('class="dugout"'), 2)


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

    def test_a_single_and_a_line_out_leave_from_home_plate_for_either_hand(self):
        count = {"balls": 1, "strikes": 1}
        for outcome in ("single", "line_out"):
            track = game_field.ball_track({"outcome": outcome, "batter_id": "9", "count": count})
            origins = [game_field.ball_path(track, bats)[1] for bats in ("L", "R", "S", None)]
            self.assertEqual(set(origins), {game_field.HOME}, "the hit leaves home plate, not the batter's box")
            self.assertEqual(len(game_field.ball_path(track, "L")), 3)


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

    def test_a_runner_touches_each_base_on_the_way(self):
        self.assertEqual(game_field.bases_touched("first", "third"), ("first", "second", "third"))
        self.assertEqual(game_field.bases_touched("first", "home"), ("first", "second", "third", "home"))
        self.assertEqual(game_field.bases_touched("second", "home"), ("second", "third", "home"))
        self.assertEqual(game_field.bases_touched("home", "second"), ("home", "first", "second"))
        self.assertEqual(game_field.bases_touched("home", "first"), ("home", "first"))
        self.assertEqual(game_field.bases_touched("home", "home"), ("home", "first", "second", "third", "home"))
        self.assertEqual(game_field.bases_touched("second", "second"), ("second",))
        self.assertEqual(game_field.bases_touched("first", "out"), ("first",))
