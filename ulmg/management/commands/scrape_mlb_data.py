# ABOUTME: ARCHIVED - Scrapes MLB for birthdate/position. See documents/MLB_DATA_PIPELINE_RECOMMENDATION.md
from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Scrape MLB for player info (delegates to archive)."

    def handle(self, *args, **options):
        call_command("archive_mlb_scrape_data", *args, **options)
