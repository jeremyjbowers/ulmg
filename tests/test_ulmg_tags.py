# ABOUTME: Tests for custom template filters in ulmg_tags.

from django.test import SimpleTestCase

from ulmg.templatetags.ulmg_tags import ops_plus


class OpsPlusFilterTestCase(SimpleTestCase):
    def test_returns_stored_ops_plus_when_present(self):
        self.assertEqual(ops_plus({"ops_plus": 128}), 128)

    def test_derives_ops_plus_from_obp_plus_and_slg_plus(self):
        self.assertEqual(
            ops_plus({"obp_plus": 120, "slg_plus": 130}),
            150,
        )

    def test_returns_none_when_components_missing(self):
        self.assertIsNone(ops_plus({"obp_plus": 120}))
        self.assertIsNone(ops_plus(None))
