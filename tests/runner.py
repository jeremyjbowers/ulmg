# ABOUTME: The project's Django test runner: Django's DiscoverRunner with autovacuum turned off in the test database.
# ABOUTME: Off before --parallel clones the database, so each worker's copy is off too and the planner keeps sane estimates.

from django.db import connections
from django.db.models.signals import post_migrate
from django.test.runner import DiscoverRunner


def disable_autovacuum(using):
    """
    Turn autovacuum off for every table in a Postgres test database.

    Each TestCase class builds its rows inside a transaction and rolls them
    back. When autovacuum visits a table that holds only those rolled-back
    rows while another class's transaction keeps it from truncating the
    table, it records the table as holding no rows on its pages. The planner
    then expects one row however many the next class inserts, and picks
    nested loops that scan whole tables per row: a query on the generated
    schedule took seconds instead of milliseconds. A never-vacuumed table is
    estimated from its size instead, which keeps the plans sane.
    """
    connection = connections[using]
    if connection.vendor != "postgresql":
        return
    with connection.cursor() as cursor:
        for table in connection.introspection.table_names(cursor):
            cursor.execute(f"ALTER TABLE {connection.ops.quote_name(table)} SET (autovacuum_enabled = false)")


class ProjectTestRunner(DiscoverRunner):
    """DiscoverRunner, with autovacuum off in each test database before any parallel clones are made."""

    def setup_databases(self, **kwargs):
        done = set()

        def after_migrate(sender, using, **signal_kwargs):
            # migrate sends this once per app; the tables only need it once.
            if using not in done:
                done.add(using)
                disable_autovacuum(using)

        post_migrate.connect(after_migrate, weak=False, dispatch_uid="tests.runner.disable_autovacuum")
        try:
            return super().setup_databases(**kwargs)
        finally:
            post_migrate.disconnect(dispatch_uid="tests.runner.disable_autovacuum")
