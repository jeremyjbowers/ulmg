from django.apps import apps
from django.db import connection
from django.db.models import Avg, Sum, Count
from django.core.management.base import BaseCommand, CommandError

from ulmg import utils


class Command(BaseCommand):
    def handle(self, *args, **options):
        utils.reset_player_stats()
