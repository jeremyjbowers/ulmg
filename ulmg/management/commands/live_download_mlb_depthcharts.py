# ABOUTME: Delegates to archive_mlb_live_download_depthcharts. See documents/MLB_DATA_PIPELINE_RECOMMENDATION.md
# ABOUTME: Will be refactored into live_download_mlb_rosters per recommendation.
from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Download MLB 40-man rosters (delegates to archive). See MLB_DATA_PIPELINE_RECOMMENDATION.md"

    def handle(self, *args, **options):
        call_command("archive_mlb_live_download_depthcharts", *args, **options)
