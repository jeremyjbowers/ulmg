import csv

from django.core.management.base import BaseCommand, CommandError
from ulmg import models


class Command(BaseCommand):

    def handle(self, *args, **options):
        hitters = [p.stats for p in models.Player.objects.filter(owned=False).exclude(position="P") if "siera" not in p.stats]
        pitchers = [p.stats for p in models.Player.objects.filter(owned=False).filter(position="P")]

        with open('data/unowned.hitters.csv', 'w') as writefile:
            fieldnames = list(hitters[0].keys())
            writer = csv.DictWriter(writefile, fieldnames=fieldnames)
            writer.writeheader()
            for h in hitters:
                writer.writerow(h)

        with open('data/unowned.pitchers.csv', 'w') as writefile:
            fieldnames = list(pitchers[0].keys())
            writer = csv.DictWriter(writefile, fieldnames=fieldnames)
            writer.writeheader()
            for h in pitchers:
                if not h.get('rbi'):
                    writer.writerow(h)