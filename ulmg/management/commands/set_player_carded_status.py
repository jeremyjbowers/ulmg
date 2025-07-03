from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q
from django.db import transaction

from ulmg import models


class Command(BaseCommand):
    help = 'Set is_carded=True for PlayerStatSeason records where player had MLB appearances'

    def add_arguments(self, parser):
        parser.add_argument(
            '--season',
            type=int,
            help='Specific season to process (default: all seasons)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be updated without making changes',
        )

    def handle(self, *args, **options):
        season = options.get('season')
        dry_run = options.get('dry_run')

        # Base queryset for PlayerStatSeason records
        queryset = models.PlayerStatSeason.objects.filter(
            classification='1-majors'  # Only look at MLB-level records
        )

        if season:
            queryset = queryset.filter(season=season)
            self.stdout.write(f"Processing season {season}")
        else:
            self.stdout.write("Processing all seasons")

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN MODE - No changes will be made"))

        # Find PlayerStatSeason records that should be marked as carded
        # A player is "carded" if they had any MLB appearances (PA or IP)
        carded_records = queryset.filter(
            Q(hit_stats__pa__gt=0) |  # Had plate appearances
            Q(pitch_stats__ip__gt=0) |  # Had innings pitched
            Q(hit_stats__g__gt=0) |  # Had games played
            Q(pitch_stats__g__gt=0)  # Had games pitched
        ).exclude(carded=True)  # Only update records not already marked as carded

        # Find PlayerStatSeason records that should NOT be marked as carded
        # A player is NOT carded if they had NO MLB appearances (PA, IP, or G are null or 0)
        not_carded_records = queryset.filter(
            (
                # All null stats
                (Q(hit_stats__pa__isnull=True) & Q(pitch_stats__ip__isnull=True) &
                 Q(hit_stats__g__isnull=True) & Q(pitch_stats__g__isnull=True)) |
                # OR all zero stats
                (Q(hit_stats__pa=0) & Q(pitch_stats__ip=0) &
                 Q(hit_stats__g=0) & Q(pitch_stats__g=0))
            ) &
            Q(carded=True)  # Only update records currently marked as carded
        )

        self.stdout.write(f"Found {carded_records.count()} records to mark as carded")
        self.stdout.write(f"Found {not_carded_records.count()} records to mark as not carded")

        if dry_run:
            # Show examples of what would be updated
            self.stdout.write("\nExamples of records that would be marked as CARDED:")
            for record in carded_records[:5]:
                pa = record.hit_stats.get('pa', 0) if record.hit_stats else 0
                ip = record.pitch_stats.get('ip', 0) if record.pitch_stats else 0
                g_hit = record.hit_stats.get('g', 0) if record.hit_stats else 0
                g_pitch = record.pitch_stats.get('g', 0) if record.pitch_stats else 0
                self.stdout.write(f"  {record.player.name} ({record.season}): PA={pa}, IP={ip}, G_hit={g_hit}, G_pitch={g_pitch}")

            self.stdout.write("\nExamples of records that would be marked as NOT CARDED:")
            for record in not_carded_records[:5]:
                self.stdout.write(f"  {record.player.name} ({record.season}): No MLB appearances")

        else:
            # Perform the updates
            with transaction.atomic():
                # Mark records as carded
                carded_count = carded_records.update(carded=True)
                self.stdout.write(
                    self.style.SUCCESS(f'Successfully marked {carded_count} records as carded')
                )

                # Mark records as not carded
                not_carded_count = not_carded_records.update(carded=False)
                self.stdout.write(
                    self.style.SUCCESS(f'Successfully marked {not_carded_count} records as not carded')
                )

        self.stdout.write(self.style.SUCCESS('Command completed successfully')) 