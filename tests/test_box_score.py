# ABOUTME: Unit tests for the HTML line score: nine innings, dashes for halves that have not been played.
# ABOUTME: A played zero stays 0; X is only for a home club that does not need to bat.

from django.test import SimpleTestCase

from ulmg.box_score import AWAY, HOME, SKIPPED, UNPLAYED, line_score_cells


class LineScoreCellsTest(SimpleTestCase):
    def test_a_new_game_shows_nine_innings_with_dashes_except_the_current_half(self):
        cells = line_score_cells({AWAY: {}, HOME: {}}, inning=1, half="top", final=False)
        self.assertEqual(cells["innings"], list(range(1, 10)))
        self.assertEqual(cells[AWAY], [0] + [UNPLAYED] * 8)
        self.assertEqual(cells[HOME], [UNPLAYED] * 9)

    def test_a_played_zero_stays_zero_and_future_innings_are_dashes(self):
        cells = line_score_cells({AWAY: {1: 0}, HOME: {}}, inning=1, half="bottom", final=False)
        self.assertEqual(cells[AWAY][0], 0)
        self.assertEqual(cells[HOME][0], 0)
        self.assertEqual(cells[AWAY][1], UNPLAYED)
        self.assertEqual(cells[HOME][1], UNPLAYED)

    def test_runs_in_a_played_inning_are_the_runs(self):
        cells = line_score_cells({AWAY: {1: 2}, HOME: {1: 0}}, inning=2, half="top", final=False)
        self.assertEqual(cells[AWAY][:2], [2, 0])
        self.assertEqual(cells[HOME][:2], [0, UNPLAYED])
        self.assertEqual(cells[AWAY][2], UNPLAYED)

    def test_home_does_not_bat_in_the_ninth_when_ahead(self):
        away = {i: 0 for i in range(1, 10)}
        home = {i: (1 if i in (1, 4, 7) else 0) for i in range(1, 9)}
        cells = line_score_cells({AWAY: away, HOME: home}, inning=9, half="top", final=True)
        self.assertEqual(cells[HOME][8], SKIPPED)
        self.assertEqual(len(cells["innings"]), 9)
        self.assertEqual(cells[AWAY][8], 0)

    def test_extra_innings_extend_the_line(self):
        away = {i: 0 for i in range(1, 11)}
        home = {i: 0 for i in range(1, 10)}
        cells = line_score_cells({AWAY: away, HOME: home}, inning=10, half="bottom", final=False)
        self.assertEqual(cells["innings"], list(range(1, 11)))
        self.assertEqual(cells[HOME][9], 0)
        self.assertEqual(cells[AWAY][9], 0)
