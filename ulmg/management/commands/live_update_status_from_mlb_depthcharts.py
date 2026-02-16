# ABOUTME: ARCHIVED - Reads all_mlb_rosters.json which is never created. See documents/MLB_DATA_PIPELINE_RECOMMENDATION.md
# ABOUTME: Delegates to archive. Refactor live_download_mlb_rosters to CREATE this file first.
from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Update roster status from MLB data (delegates to archive). all_mlb_rosters.json must exist."

    def handle(self, *args, **options):
        call_command("archive_mlb_update_status_from_depthcharts", *args, **options)
