# ABOUTME: Tests how live_update_stats_from_fg_stats processes FanGraphs values before storing them.
# ABOUTME: Innings round up to the next whole inning; other counting stats stay whole numbers.
from django.test import SimpleTestCase

from ulmg.management.commands.live_update_stats_from_fg_stats import Command


class InningsValueTests(SimpleTestCase):
    def setUp(self):
        self.command = Command()

    def test_partial_innings_round_up(self):
        self.assertEqual(self.command._process_v("IP", 174.2), 175)
        self.assertEqual(self.command._process_v("IP", 69.1), 70)

    def test_partial_innings_as_text_round_up(self):
        self.assertEqual(self.command._process_v("IP", "49.2"), 50)

    def test_whole_innings_stay_whole(self):
        self.assertEqual(self.command._process_v("IP", 70.0), 70)
        self.assertEqual(self.command._process_v("IP", 0), 0)

    def test_missing_innings_are_zero(self):
        self.assertEqual(self.command._process_v("IP", None), 0)
        self.assertEqual(self.command._process_v("IP", ""), 0)


class CountingValueTests(SimpleTestCase):
    def setUp(self):
        self.command = Command()

    def test_counting_stats_stay_whole_numbers(self):
        self.assertEqual(self.command._process_v("GS", "31"), 31)
        self.assertEqual(self.command._process_v("SO", 212.0), 212)

    def test_other_keys_pass_through(self):
        self.assertEqual(self.command._process_v("ERA", 3.21), 3.21)
