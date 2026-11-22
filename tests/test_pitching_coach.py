# ABOUTME: Tests the pitching coach's lines: a fixed bench, the Bull Durham one, and the same moment twice.
# ABOUTME: No database. The game page test checks that a forced pitching change actually says one.

from django.test import SimpleTestCase

from ulmg import pitching_coach


class PitchingCoachTest(SimpleTestCase):
    def test_the_coach_has_a_bench_of_lines_including_the_eyelids(self):
        self.assertGreaterEqual(len(pitching_coach.SAYINGS), 20)
        self.assertLessEqual(len(pitching_coach.SAYINGS), 25)
        self.assertEqual(len(set(pitching_coach.SAYINGS)), len(pitching_coach.SAYINGS))
        self.assertIn("He says he's having trouble breathing out of his eyelids.", pitching_coach.SAYINGS)

    def test_the_same_moment_always_gets_the_same_line(self):
        first = pitching_coach.saying(12, 34, "he has reached his limit")
        self.assertEqual(first, pitching_coach.saying(12, 34, "he has reached his limit"))
        self.assertIn(first, pitching_coach.SAYINGS)

    def test_different_pitchers_are_not_all_handed_the_same_line(self):
        lines = {pitching_coach.saying(1, pitcher_id, "out of innings") for pitcher_id in range(80)}
        self.assertGreater(len(lines), 1)
