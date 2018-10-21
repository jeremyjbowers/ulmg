from django.core.management.base import BaseCommand, CommandError
from ulmg import models


class Command(BaseCommand):
    def handle(self, *args, **options):
        for p in models.Player.objects.all():
            p.save()