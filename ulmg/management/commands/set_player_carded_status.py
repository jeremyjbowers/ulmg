from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from ulmg import models, utils


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
            classification__in=["1-mlb", "1-majors"]
        )

        if season:
            queryset = queryset.filter(season=season)
            self.stdout.write(f"Processing season {season}")
        else:
            self.stdout.write("Processing all seasons")

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN MODE - No changes will be made"))

        # Find PlayerStatSeason records that should be marked as carded
        carded_records = queryset.filter(
            utils.mlb_appearances_q()
        ).exclude(carded=True)

        # Find PlayerStatSeason records that should NOT be marked as carded
        not_carded_records = queryset.filter(
            utils.mlb_appearances_q().negated(),
            carded=True,
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