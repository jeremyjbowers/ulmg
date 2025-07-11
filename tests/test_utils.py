from django.test import TestCase
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
