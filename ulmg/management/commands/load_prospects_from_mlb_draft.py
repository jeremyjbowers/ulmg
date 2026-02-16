# ABOUTME: ARCHIVED - Scrapes MLB draft prospects. See documents/MLB_DATA_PIPELINE_RECOMMENDATION.md
from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Load draft prospects from MLB (delegates to archive)."

    def handle(self, *args, **options):
        call_command("archive_mlb_load_prospects_draft", *args, **options)
