import csv
import json
import os
from decimal import Decimal

from dateutil.parser import parse
from django.apps import apps
from django.db import connection
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from nameparser import HumanName

from ulmg import models


class Command(BaseCommand):

    def handle(self, *args, **options):
        hitters = [
            ('Brian O\'Grady','16729'),
            ('Christian Colon','11145'),
            ('Wilkin Castillo','5124'),
            ('Ronald Bolanos','20041'),
            ('Deivy Grullon','15988'),
            ('Yasmany Tomas','17171'),
            ('Ruben Tejada','5519')
        ]
        pitchers = [
            ('Cole Sulser','15256'),
            ('Art Warren','18251'),
            ('Bryan Abreu','16609'),
            ('Hunter Harvey','15507'),
            ('Pedro Avila','18864'),
            ('James Karinchak','20151'),
            ('Jeremy Walker','19981'),
            ('Justin Dunn','19268'),
            ('Wei-Chieh Huang','17508'),
            ('Enderson Franco','11896'),
            ('Brian Schlitter','3599'),
            ('Buddy Boshers','8490'),
            ('Zac Grotz','18256'),
            ('Fernando Abad','4994'),
            ('Jimmy Herget','17556'),
            ('Brian Moran','9646'),
            ('Jonathan Hernandez','17464'),
            ('Jose Cisnero','6399'),
            ('Sam Selman','13397'),
            ('Jacob Waguespack','18318'),
            ('Jay Jackson','7432'),
            ('Brandon Brennan','13527'),
            ('Matt Carasiti','13276'),
            ('Brusdar Graterol','20367'),
            ('Joel Kuhnel','19995'),
            ('T.J. Zeuch','19269'),
            ('Tyler Alexander','17735'),
            ('Asher Wojciechowski','10836'),
            ('Joe Harvey','16459'),
            ('Conner Menez','19199'),
            ('Junior Fernandez','18496'),
            ('Locke St. John','16850'),
            ('David McKay','19814'),
            ('Cy Sneed','16106'),
            ('Travis Bergen','18581'),
            ('Chris Mazza','14151'),
            ('Pedro Payano','18313'),
            ('Jose Quijada','19200'),
            ('Edgar Garcia','19276'),
            ('Anthony Kay','20387'),
            ('Josh A. Smith','10946'),
            ('Eduardo Jimenez','19642'),
            ('Branden Kline','14101'),
            ('Ronald Bolanos','20041'),
            ('Reggie McClain','19311'),
            ('John Schreiber','20020'),
            ('Josh D. Smith','13629'),
            ('Dillon Tate','17796'),
            ('Tom Eshelman','18361'),
            ('David Bednar','19569'),
            ('Chandler Shepherd','16166'),
            ('Rookie Davis','14962'),
            ('Peter Fairbanks','17998'),
            ('Manny Banuelos','5365'),
            ('Michael Blazek','9654'),
            ('Kyle Dowdy','19285'),
            ('Gabe Speier','17170'),
            ('Phillip Diehl','20030'),
            ('Sean Poppen','19583'),
            ('Gerardo Reyes','16306'),
            ('Jordan Romano','16122'),
            ('Parker Markel','12106'),
            ('Kyle Bird','16618'),
            ('Luis Escobar','17345'),
            ('Josh Sborz','18323'),
            ('Reed Garrett','16866'),
            ('James Marvel','19675'),
            ('Hector Noesi','3292'),
            ('Trevor Kelley','18454'),
            ('Joseph Palumbo','17035'),
            ('Ruben Alaniz','10819'),
            ('Montana DuRapau','16768'),
            ('Adrian Morejon','20039'),
            ('Rico Garcia','20023'),
            ('Miguel Del Pozo','18792'),
            ('Kyle Zimmer','14169'),
            ('Stephen Nogosek','19545'),
            ('Ryan Feierabend','6336'),
            ('Bryan Garcia','19457'),
            ('Tayler Scott','13652'),
            ('Brady Rodgers','13393')
        ]

        for p in hitters:
            players = models.Player.objects.filter(name=p[0])

            if len(players) == 1:
                obj = players[0]
                obj.fg_id = p[1]
                obj.save()

            if len(players) == 0:
                name = HumanName(p[0])
                obj = models.Player()
                obj.first_name = name.first
                obj.last_name = name.last
                obj.position = "P"
                obj.level = "B"
                obj.fg_id = p[1]
                obj.save()

            print(obj)

        for p in pitchers:
            players = models.Player.objects.filter(name=p[0])

            if len(players) == 1:
                obj = players[0]
                obj.fg_id = p[1]
                obj.save()

            if len(players) == 0:
                name = HumanName(p[0])
                obj = models.Player()
                obj.first_name = name.first
                obj.last_name = name.last
                obj.position = "P"
                obj.level = "B"
                obj.fg_id = p[1]
                obj.save()

            print(obj)