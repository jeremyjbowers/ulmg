from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from django.db.models import Count

import requests
from bs4 import BeautifulSoup

from ulmg import models, utils


class Command(BaseCommand):
    def fix_fg_dupes(self):
        d1 = (
            models.Player.objects.exclude(fg_id__isnull=True).values('fg_id')
            .annotate(count=Count('id'))
            .values('fg_id')
            .order_by()
            .filter(count__gt=1)
        )

        print(f"initial duplicates: {d1.count()}")
        for d in d1:
            print(d)
            objs = models.Player.objects.filter(fg_id=d['fg_id'])
            # for o in objs:
            #     # if not o.team:
            #     #     o.delete()

        d2 = (
            models.Player.objects.exclude(fg_id__isnull=True).values('fg_id')
            .annotate(count=Count('id'))
            .values('fg_id')
            .order_by()
            .filter(count__gt=1)
        ) 

        print(f"remaining duplicates: {d2.count()}")
        # for d in d2:
        #     print(d)

    def fix_mlbam_dupes(self):
        d1 = (
            models.Player.objects.exclude(mlbam_id__isnull=True).values('mlbam_id')
            .annotate(count=Count('id'))
            .values('mlbam_id')
            .order_by()
            .filter(count__gt=1)
        )

        print(f"initial duplicates: {d1.count()}")
        for d in d1:
            objs = models.Player.objects.filter(mlbam_id=d['mlbam_id'])
            for o in objs:
                if not o.team and not o.fg_id:
                    o.delete()

        d2 = (
            models.Player.objects.exclude(mlbam_id__isnull=True).values('mlbam_id')
            .annotate(count=Count('id'))
            .values('mlbam_id')
            .order_by()
            .filter(count__gt=1)
        ) 

        print(f"remaining duplicates: {d2.count()}")
        for d in d2:
            print(d)

    def handle(self, *args, **options):
        self.fix_mlbam_dupes()
        # self.fix_fg_dupes()