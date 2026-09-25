# ABOUTME: django-admin wrapper to launch the ULMG stdio MCP server.
# ABOUTME: Prefer the `ulmg-mcp` console script; this exists for discoverability.
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = (
        "Run the ULMG stdio MCP server (requires ULMG_API_URL and ULMG_API_TOKEN). "
        "Usually invoked via the `ulmg-mcp` entry point from Cursor."
    )

    def handle(self, *args, **options):
        from ulmg.mcp.server import main

        main()
