from django.core.management.base import BaseCommand, CommandError
from ulmg import models

class Command(BaseCommand):

    def handle(self, *args, **options):
        for p in models.Player.objects.filter(level__in=["A","V"]):
            p.is_carded = True
            p.save()

        for p in models.Player.objects.filter(level__in=['B']):
            if p.stats:
                p.is_carded = True
                p.save()