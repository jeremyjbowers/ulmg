from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from django.db.models import Count

from ulmg import models, utils


class Command(BaseCommand):

    def handle(self, *args, **options):
        for p in models.Player.objects.all():
            p.save()