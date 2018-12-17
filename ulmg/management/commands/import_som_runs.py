import csv

from django.core.management.base import BaseCommand, CommandError

from ulmg import models


class Command(BaseCommand):
    season = 2018
    
    def handle_runs(self, p):
        p_dict = {}
        p_obj = models.Player.objects.get(fg_id=p['id'])
        p_dict['player'] = p_obj

        if p['pos'] != "P":
            if p['pa'] != "":
                p_dict['raar'] = p['raar']
                p_dict['raal'] = p['raal']
                p_dict['raat'] = p['raat']
                p_dict['season'] = self.season
                obj = models.SomRunsYear(**p_dict)
                obj.save()

                p_obj.raar = p['raar']
                p_obj.raal = p['raal']
                p_obj.raat = p['raat']
                p_obj.save()

        if p['pos'] == "P":
            if (p['ip'] != "") or (p['st'] != ""):
                p_dict['raar'] = p['raar']
                p_dict['raal'] = p['raal']
                p_dict['raat'] = p['raat']
                p_dict['season'] = self.season
                obj = models.SomRunsYear(**p_dict)
                obj.save()

                p_obj.raar = p['raar']
                p_obj.raal = p['raal']
                p_obj.raat = p['raat']
                p_obj.save()


    def handle(self, *args, **options):
        models.SomRunsYear.objects.filter(season=self.season).delete()
        models.Player.objects.update(raar=None, raal=None, raat=None)

        with open('data/som-%s-runs.csv' % self.season, 'r') as readfile:
            players = [dict(p) for p in csv.DictReader(readfile)]
            for p in players:
                print("%(first_name)s %(last_name)s" % p)
                self.handle_runs(p)

        with open('data/som-%s-runs-unowned.csv' % self.season, 'r') as readfile:
            players = [dict(p) for p in csv.DictReader(readfile)]
            for p in players:
                print("%(first_name)s %(last_name)s" % p)
                self.handle_runs(p)