import csv
import ujson as json

from django.core.management.base import BaseCommand, CommandError
from ulmg import models


class Command(BaseCommand):

    def handle(self, *args, **options):
        chitters = [{"stats": p.steamer_predix, "pos": p.position, "level": p.level} for p in models.Player.objects.exclude(steamer_predix__isnull=True).exclude(is_owned=True).filter(is_carded=True, steamer_predix__AB__isnull=False)]
        cpitchers = [{"stats": p.steamer_predix, "pos": p.position, "level": p.level} for p in models.Player.objects.exclude(steamer_predix__isnull=True).exclude(is_owned=True).filter(is_carded=True, steamer_predix__IP__isnull=False)]
        uhitters = [{"stats": p.steamer_predix, "pos": p.position, "level": p.level} for p in models.Player.objects.exclude(steamer_predix__isnull=True).exclude(is_owned=True).filter(is_carded=False, steamer_predix__AB__isnull=False)]
        upitchers = [{"stats": p.steamer_predix, "pos": p.position, "level": p.level} for p in models.Player.objects.exclude(steamer_predix__isnull=True).exclude(is_owned=True).filter(is_carded=False, steamer_predix__IP__isnull=False)]

        with open('data/unowned.hitters.carded.csv', 'w') as writefile:
            a = ["level", "pos"] 
            a += [f for f in list(chitters[0]['stats'].keys())]
            writer = csv.DictWriter(writefile, fieldnames=a)
            writer.writeheader()
            chitters = sorted(chitters, key=lambda x:float(x['stats']['WAR']), reverse=True)
            for h in chitters:
                payload = h['stats']
                payload['level'] = h['level']
                payload['pos'] = h['pos']
                writer.writerow(payload)

        with open('data/unowned.pitchers.carded.csv', 'w') as writefile:
            b = ["level", "pos"] 
            b += [f for f in list(cpitchers[0]['stats'].keys())]
            writer = csv.DictWriter(writefile, fieldnames=b)
            writer.writeheader()
            cpitchers = sorted(cpitchers, key=lambda x:float(x['stats']['WAR']), reverse=True)
            for h in cpitchers:
                payload = h['stats']
                payload['level'] = h['level']
                payload['pos'] = h['pos']
                writer.writerow(payload)

        with open('data/unowned.hitters.uncarded.csv', 'w') as writefile:
            c = ["level", "pos"] 
            c += [f for f in list(uhitters[0]['stats'].keys())]
            writer = csv.DictWriter(writefile, fieldnames=c)
            writer.writeheader()
            uhitters = sorted(uhitters, key=lambda x:float(x['stats']['WAR']), reverse=True)
            for h in uhitters:
                payload = h['stats']
                payload['level'] = h['level']
                payload['pos'] = h['pos']
                if int(payload['AB']) > 50.0:
                    writer.writerow(payload)

        with open('data/unowned.pitchers.uncarded.csv', 'w') as writefile:
            d = ['level', 'pos']
            d += [f for f in list(upitchers[0]['stats'].keys())]
            writer = csv.DictWriter(writefile, fieldnames=d)
            writer.writeheader()
            upitchers = sorted(upitchers, key=lambda x:float(x['stats']['WAR']), reverse=True)
            for h in upitchers:
                payload = h['stats']
                payload['level'] = h['level']
                payload['pos'] = h['pos']
                if float(payload['IP']) > 25.0:
                    writer.writerow(payload)