from django.core.management.base import BaseCommand, CommandError
from ulmg import models

class Command(BaseCommand):

    def handle(self, *args, **options):
        for p in models.Player.objects.all():
            p.is_prospect = False
            if p.fg_prospect_rank or p.ba_prospect_rank or p.mlb_prospect_rank:
                p.is_prospect = True
            p.save()