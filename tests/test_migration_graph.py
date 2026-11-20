# ABOUTME: The ulmg migration graph has a single leaf so a deploy can migrate.
# ABOUTME: Depth charts and advanced bullpen usage each added an 0111, and the merge joins them.

from django.db.migrations.loader import MigrationLoader
from django.test import TestCase


class MigrationGraphTest(TestCase):
    def test_ulmg_has_one_leaf(self):
        loader = MigrationLoader(None, ignore_no_migrations=True)
        leaves = [name for app, name in loader.graph.leaf_nodes() if app == "ulmg"]
        self.assertEqual(
            leaves,
            ["0112_merge_0111_depth_chart_0111_halfplan_bullpen_rules"],
        )
