from django.core.management.base import BaseCommand
from django.db.models import Count, Max
from ulmg import models


class Command(BaseCommand):
    help = 'Deduplicate PlayerStatSeason records, keeping the most recent for each (player, season, classification) combination'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without actually deleting',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        # Find duplicates by grouping on player, season, classification
        # and counting records with more than 1 occurrence
        duplicates = (
            models.PlayerStatSeason.objects
            .values('player', 'season', 'classification')
            .annotate(count=Count('id'), max_id=Max('id'))
            .filter(count__gt=1)
        )

        total_duplicates = duplicates.count()
        total_records_to_delete = 0
        
        if total_duplicates == 0:
            self.stdout.write(
                self.style.SUCCESS("No duplicate PlayerStatSeason records found!")
            )
            return

        self.stdout.write(
            self.style.WARNING(f"Found {total_duplicates} sets of duplicate records")
        )

        for duplicate_group in duplicates:
            player_id = duplicate_group['player']
            season = duplicate_group['season']
            classification = duplicate_group['classification']
            count = duplicate_group['count']
            max_id = duplicate_group['max_id']
            
            # Get player name for better logging
            try:
                player = models.Player.objects.get(id=player_id) if player_id else None
                player_name = player.name if player else "Unknown Player"
            except models.Player.DoesNotExist:
                player_name = "Unknown Player"
            
            self.stdout.write(
                f"  Player: {player_name} (ID: {player_id}), "
                f"Season: {season}, Classification: {classification} - "
                f"{count} duplicates"
            )
            
            # Find all records for this combination except the newest one
            records_to_delete = (
                models.PlayerStatSeason.objects
                .filter(
                    player_id=player_id,
                    season=season, 
                    classification=classification
                )
                .exclude(id=max_id)
            )
            
            records_to_delete_count = records_to_delete.count()
            total_records_to_delete += records_to_delete_count
            
            if dry_run:
                self.stdout.write(f"    Would delete {records_to_delete_count} old records")
                for record in records_to_delete:
                    self.stdout.write(f"      - Record ID {record.id} (created: {record.created})")
            else:
                # Show which record we're keeping
                kept_record = models.PlayerStatSeason.objects.get(id=max_id)
                self.stdout.write(f"    Keeping record ID {max_id} (created: {kept_record.created})")
                self.stdout.write(f"    Deleting {records_to_delete_count} old records")
                
                # Delete the older records
                records_to_delete.delete()

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"DRY RUN: Would delete {total_records_to_delete} duplicate records total. "
                    f"Run without --dry-run to actually delete them."
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Successfully deleted {total_records_to_delete} duplicate records!"
                )
            ) 