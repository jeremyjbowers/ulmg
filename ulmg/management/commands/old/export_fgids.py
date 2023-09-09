import ujson as json

from django.core.management.base import BaseCommand, CommandError
from ulmg import models


class Command(BaseCommand):
    def handle(self, *args, **options):
        with open('fgid_crosswalk.json', 'w') as writefile:
            writefile.write(json.dumps([{"mlb_id": p.mlbam_id, "fg_id": p.fg_id} for p in models.Player.objects.filter(fg_id__isnull=False, mlbam_id__isnull=False)]))