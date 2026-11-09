# ABOUTME: Tests the pixel field: where the defenders and runners stand, and the ball path drawn from an outcome.
# ABOUTME: The path is a picture of the result, so the same outcome and seed always land in the same place.

from django.test import SimpleTestCase

from ulmg import field_view


def scoreboard():
    return {
        "away": "ATL", "home": "HCH", "away_score": 1, "home_score": 0,
        "half": "Top", "inning": 1, "outs": 1,
    }


class FieldViewTestCase(SimpleTestCase):
    def fielders(self):
        return [
            {"position": position, "name": f"ATL {position}", "rating": 1.5 if position == "SS" else None}
            for position in ("C", "1B", "2B", "3B", "SS", "LF", "CF", "RF", "DH")
        ]

    def scene(self, **kwargs):
        values = dict(
            fielders=self.fielders(),
            runners={"first": "Dee Runner", "second": None},
            batter={"name": "Cal Hitter", "bats": "L"},
            pitcher={"name": "Ada Starter"},
            last_play=None,
            scoreboard=scoreboard(),
        )
        values.update(kwargs)
        return field_view.scene(**values)

    def test_the_defense_stands_at_its_positions_and_a_runner_stands_on_his_base(self):
        picture = self.scene()
        spots = {fielder["position"]: (fielder["x"], fielder["y"]) for fielder in picture["fielders"]}
        self.assertEqual(set(spots), {"C", "1B", "2B", "3B", "SS", "LF", "CF", "RF"})
        self.assertEqual(len(set(spots.values())), 8)
        self.assertEqual(spots["SS"], field_view.SPOTS["SS"])
        short = next(fielder for fielder in picture["fielders"] if fielder["position"] == "SS")
        self.assertEqual(short["rating"], "+1.5")
        self.assertEqual(picture["runners"], [
            {"base": "first", "name": "Runner", "x": field_view.BASE_SPOTS["first"][0], "y": field_view.BASE_SPOTS["first"][1]}
        ])
        self.assertEqual(picture["batter"]["x"], field_view.BATTER_BOX["L"][0])
        self.assertEqual(picture["pitcher"]["name"], "Starter")

    def test_a_batted_ball_sprays_by_its_outcome_and_a_strikeout_is_the_pitch(self):
        single = field_view.ball_path("single", seed=7)
        self.assertEqual(single["points"][0], field_view.HOME)
        self.assertEqual(single["kind"], "line")
        self.assertIn("Single to ", single["caption"])
        self.assertEqual(field_view.ball_path("single", seed=7), single)
        other = field_view.ball_path("single", seed=8)
        self.assertNotEqual(other["points"], single["points"])

        strikeout = field_view.ball_path("strikeout", seed=1)
        self.assertEqual(strikeout["points"], [field_view.SPOTS["P"], field_view.HOME])
        self.assertEqual(strikeout["caption"], "Strikeout")
        homer = field_view.ball_path("home_run", seed=3)
        self.assertEqual(homer["kind"], "fly")
        self.assertLess(homer["points"][-1][1], field_view.DEEP[2][1])

    def test_a_half_inning_with_no_hand_played_ball_draws_no_path(self):
        picture = self.scene(last_play=None)
        self.assertIsNone(picture["ball"])
        self.assertEqual(picture["caption"], "")
        played = self.scene(last_play={"outcome": "ground_out", "seed": 4})
        self.assertEqual(played["ball"]["kind"], "ground")
        self.assertIn("Ground out to ", played["caption"])
