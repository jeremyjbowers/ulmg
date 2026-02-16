# ABOUTME: ARCHIVED - Stub that reads all_mlb_rosters.json. See documents/MLB_DATA_PIPELINE_RECOMMENDATION.md
from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Load players from MLB depth charts (delegates to archive)."

    def handle(self, *args, **options):
        call_command("archive_mlb_load_players_from_depthcharts", *args, **options)
