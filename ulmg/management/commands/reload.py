import os
from io import StringIO
os.environ['DJANGO_COLORS'] = 'nocolor'

from django.apps import apps
from django.db import connection
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from ulmg import models


class Command(BaseCommand):

    def handle(self, *args, **options):
        models.Player.objects.all().delete()
        models.Team.objects.all().delete()

        commands = StringIO()
        cursor = connection.cursor()

        for app in apps.get_app_configs():
            label = app.label
            call_command('sqlsequencereset', label, stdout=commands)

        cursor.execute(commands.getvalue())

        call_command('loaddata', 'data/fixtures/ulmg.json')