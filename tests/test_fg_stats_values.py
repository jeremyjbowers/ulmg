# ABOUTME: Tests how live_update_stats_from_fg_stats processes FanGraphs values before storing them.
# ABOUTME: Innings keep FanGraphs' exact .1/.2 notation; other counting stats stay whole numbers.
from django.test import SimpleTestCase

from ulmg.management.commands.live_update_stats_from_fg_stats import Command
from ulmg.usage import innings_to_outs


class InningsValueTests(SimpleTestCase):
    def setUp(self):
        self.command = Command()

    def test_partial_innings_are_kept_exactly(self):
        self.assertEqual(self.command._process_v("IP", 174.2), 174.2)
        self.assertEqual(self.command._process_v("IP", 69.1), 69.1)

    def test_partial_innings_as_text_are_kept_exactly(self):
        self.assertEqual(self.command._process_v("IP", "49.2"), 49.2)

    def test_whole_innings_stay_whole(self):
        self.assertEqual(self.command._process_v("IP", 70.0), 70.0)
        self.assertEqual(self.command._process_v("IP", 0), 0)

    def test_missing_innings_are_zero(self):
        self.assertEqual(self.command._process_v("IP", None), 0)
        self.assertEqual(self.command._process_v("IP", ""), 0)

    def test_stored_innings_count_every_out_and_stay_under_the_next_threshold(self):
        outs = innings_to_outs(self.command._process_v("IP", 174.2))
        self.assertEqual(outs, 524)
        self.assertLess(outs, 175 * 3)


class CountingValueTests(SimpleTestCase):
    def setUp(self):
        self.command = Command()

    def test_counting_stats_stay_whole_numbers(self):
        self.assertEqual(self.command._process_v("GS", "31"), 31)
        self.assertEqual(self.command._process_v("SO", 212.0), 212)

    def test_other_keys_pass_through(self):
        self.assertEqual(self.command._process_v("ERA", 3.21), 3.21)
