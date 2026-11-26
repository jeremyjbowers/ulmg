# ABOUTME: The ulmg migration graph has a single leaf so a deploy can migrate.
# ABOUTME: A second head would leave the deploy unsure which migration to run.

from django.db.migrations.loader import MigrationLoader
from django.test import TestCase


class MigrationGraphTest(TestCase):
    def test_ulmg_has_one_leaf(self):
        loader = MigrationLoader(None, ignore_no_migrations=True)
        leaves = [name for app, name in loader.graph.leaf_nodes() if app == "ulmg"]
        self.assertEqual(
            leaves,
            ["0114_owner_stats_view"],
        )
