from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from ulmg import models


class Command(BaseCommand):

    def handle(self, *args, **options):
        models.Player.objects.all().delete()
        models.Team.objects.all().delete()
        call_command('loaddata', 'data/fixtures/ulmg.json')