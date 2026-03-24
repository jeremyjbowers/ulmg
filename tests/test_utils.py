from django.test import TestCase, override_settings

from ulmg import utils


class UtilsTestCase(TestCase):
    """Test utility functions"""
    
    def test_normalized_pos(self):
        for p in ["1B", "2B", "3B", "SS"]:
            self.assertEqual(utils.normalize_pos(p), "IF")
            self.assertEqual(utils.normalize_pos(p.lower()), "IF")

        for p in ["RF", "CF", "LF"]:
            self.assertEqual(utils.normalize_pos(p), "OF")
            self.assertEqual(utils.normalize_pos(p.lower()), "OF")

    def test_str_to_bool(self):
        for b in ["y", "yes", "t", "true"]:
            self.assertEqual(utils.str_to_bool(b), True)
            self.assertEqual(utils.str_to_bool(b.upper()), True)

        for b in ["n", "no", "f", "false"]:
            self.assertEqual(utils.str_to_bool(b), False)
            self.assertEqual(utils.str_to_bool(b.upper()), False)

        for b in ["nope", "yup", "yessir", 12345, True]:
            self.assertEqual(utils.str_to_bool(b), None)

    @override_settings(CURRENT_SEASON=2026, CURRENT_SEASON_TYPE="offseason")
    def test_get_current_season_offseason_is_prior_year_for_stats(self):
        self.assertEqual(utils.get_current_season(), 2025)

    @override_settings(CURRENT_SEASON=2026, CURRENT_SEASON_TYPE="midseason")
    def test_get_current_season_midseason_matches_current_season(self):
        self.assertEqual(utils.get_current_season(), 2026)
