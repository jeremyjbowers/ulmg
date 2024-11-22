from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from django.db.models import Count

from ulmg import models, utils


class Command(BaseCommand):
    def fix_trades(self, *args, **options):
        for trade in models.Trade.objects.all():
            trade.set_trade_summary()
            trade.set_teams()
            trade.save()

    def handle(self, *args, **options):
        self.fix_trades(*args, **options)