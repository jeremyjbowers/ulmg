from django.core.management.base import BaseCommand, CommandError
from django.db.models import Count, Avg, Sum, Max, Min, Q

import ujson as json
from ulmg import models

class Command(BaseCommand):
    steamer_dirty_hit_path = 'data/steamer_hitters_2019predix.csv'
    steamer_dirty_pitch_path = 'data/steamer_pitcherss_2019predix.csv'

    def handle(self, *args, **options):
        dupes = models.Player.objects.values('name').annotate(Count('id')).order_by().filter(id__count__gt=1)
        print("Found %s names with a duplicate" % len(dupes))

        dupe_list = models.Player.objects.filter(name__in=[item['name'] for item in dupes])

        print("Found %s players possibly affected" % len(dupe_list))

        with open('data/django_dupes.json', 'w') as writefile:
            writefile.write(json.dumps([{"name": d.name, "pk": d.id, "fg_id": d.fangraphs_id, "fg_url": d.fangraphs_url} for d in dupe_list]))