# ABOUTME: Tests the project's test runner: every table in the test database has autovacuum turned off.
# ABOUTME: Reads the real table options from Postgres's catalog for the database these tests run in.

from django.conf import settings
from django.db import connection
from django.test import SimpleTestCase, TestCase

from tests.runner import ProjectTestRunner, disable_autovacuum


def autovacuum_options():
    """{table: reloptions} for every table Django knows about in the current database."""
    with connection.cursor() as cursor:
        tables = connection.introspection.table_names(cursor)
        cursor.execute(
            "SELECT relname, reloptions FROM pg_class WHERE relkind = 'r' AND relname = ANY(%s)", [tables]
        )
        return dict(cursor.fetchall())


class TestRunnerSettingTestCase(SimpleTestCase):
    def test_the_project_runs_its_tests_with_the_project_runner(self):
        self.assertEqual(settings.TEST_RUNNER, "tests.runner.ProjectTestRunner")


class AutovacuumTestCase(TestCase):
    def test_every_table_in_the_test_database_has_autovacuum_off(self):
        options = autovacuum_options()
        self.assertIn("ulmg_schedulegame", options)
        self.assertIn("ulmg_usageappearance", options)
        on = sorted(table for table, opts in options.items() if "autovacuum_enabled=false" not in (opts or []))
        self.assertEqual(on, [])

    def test_turning_it_off_again_is_harmless(self):
        disable_autovacuum(connection.alias)
        self.assertEqual(
            sorted(t for t, opts in autovacuum_options().items() if "autovacuum_enabled=false" not in (opts or [])),
            [],
        )

    def test_the_runner_is_django_s_discover_runner(self):
        from django.test.runner import DiscoverRunner

        self.assertTrue(issubclass(ProjectTestRunner, DiscoverRunner))
