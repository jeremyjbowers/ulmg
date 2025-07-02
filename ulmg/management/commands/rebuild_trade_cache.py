from django.core.management.base import BaseCommand
from ulmg import models


class Command(BaseCommand):
    help = "Rebuild trade cache with enhanced pick information"

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be updated without making changes',
        )
        parser.add_argument(
            '--trade-id',
            type=int,
            help='Rebuild cache for specific trade ID only',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        trade_id = options.get('trade_id')

        if trade_id:
            trades = models.Trade.objects.filter(id=trade_id)
            if not trades.exists():
                self.stdout.write(
                    self.style.ERROR(f'Trade with ID {trade_id} not found')
                )
                return
        else:
            trades = models.Trade.objects.all()

        total_trades = trades.count()
        self.stdout.write(f'Processing {total_trades} trade(s)...')

        updated_count = 0
        for trade in trades:
            old_cache = trade.trade_cache
            
            # Generate new cache
            new_cache = self.generate_enhanced_trade_cache(trade)
            
            if old_cache != new_cache:
                if dry_run:
                    self.stdout.write(
                        self.style.WARNING(
                            f'Trade {trade.id} would be updated (date: {trade.date})'
                        )
                    )
                else:
                    trade.trade_cache = new_cache
                    trade.save()
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'Updated trade {trade.id} (date: {trade.date})'
                        )
                    )
                updated_count += 1

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f'DRY RUN: {updated_count} out of {total_trades} trades would be updated'
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f'Successfully updated {updated_count} out of {total_trades} trades'
                )
            )

    def generate_enhanced_trade_cache(self, trade):
        """Generate enhanced trade cache with detailed pick information"""
        return trade.summary_dict() 