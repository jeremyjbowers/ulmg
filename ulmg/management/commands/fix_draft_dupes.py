import csv
import json
import os
from decimal import Decimal

from bs4 import BeautifulSoup
from dateutil.parser import parse
from django.apps import apps
from django.db import connection
from django.db.models import Avg, Sum, Count
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
import requests
import urllib3

from ulmg import models, utils


class Command(BaseCommand):

    def handle(self, *args, **options):
        names = ["Roman Anthony","Dylan Crews","Walker Jenkins","Jackson Jobe","Samuel Basallo","Sebastian Walcott","Kristian Campbell","Carson Williams","Andrew Painter","Bubba Chandler","Jasson Dominguez","Coby Mayo","Noah Schultz","Emmanuel Rodriguez","Jordan Lawlar","Leodalis De Vries","Max Clark","Matt Shaw","Travis Bazzana","Dalton Rushing","Colt Emerson","Aidan Miller","Bryce Eldridge","Kevin McGonigle","JJ Wetherholt","Marcelo Mayer","Josue De Paula","Chase Burns","Roki Sasaki","Kumar Rocker","Chase Dollander","Nick Kurtz","Hagen Smith","Jesus Made","Quinn Mathews","Ethan Salas","Jac Caglianone","Brandon Sproat","Chase DeLauter","Zyhir Hope","Luke Keaschall","Alejandro Rosario","Drake Baldwin","Cam Smith","Jett Williams","Kyle Teel","Thomas White","Charlie Condon","Rhett Lowder","Jacob Wilson","Cole Young","Jeferson Quero","Tink Hence","Jaison Chourio","Colson Montgomery","Jarlin Susana","Travis Sykora","Moises Ballesteros","Lazaro Montes","Xavier Isaac","Angel Genao","Edgar Quero","Cooper Pratt","Felnin Celestin","Alex Freeland","Bryce Rainer","Owen Caissie","Konnor Griffin","Jacob Misiorowski","Braden Montgomery","Cade Horton","Kevin Alcantara","Thayron Liranzo","Christian Moore","Jonny Farmelo","Brayden Taylor","Caden Dana","Agustin Ramirez","Blake Mitchell","Michael Arroyo","Adael Amador","Cam Collier","Starlyn Caba","Franklin Arias","Thomas Harrington","Josue Briceno","Brady House","Jackson Ferris","Termarr Johnson","Ronny Mauricio","Enrique Bradfield","Robert Calaz","Arjun Nimmala","Harry Ford","Colby Thomas","AJ Smith-Shawver","Justin Crawford","Demetrio Crisantes","Adrian del Castillo","Alfredo Duno","Sal Stewart","Chase Petty","Tre Morgan","Yoniel Curet","Cole Carrigg","River Ryan","Cooper Ingle","Eduardo Tait","Jefferson Rojas","Brody Hopkins","Nick Yorke","Tyler Black","James Triantos","Carter Jensen","Eduardo Quintero","Orelvis Martinez","Spencer Jones","Emil Morales","Ryan Clifford","George Lombard Jr.","Carson Benge","Ralphy Velazquez","Aidan Smith","Ryan Waldschmidt","Sean Burke","Braxton Ashcraft","Jackson Baumeister","Chandler Simpson","Noble Meyer","Jimmy Crooks","Will Warren","Luis Baez","Jake Bloss","Joe Mack","Parker Messick","Denzel Clarke","Jaden Hamm","Brice Matthews","Edwin Arroyo","Dominic Keegan","Eric Bitonti","Chayce McDermott","Luisangel Acuna","Yilber Diaz","Nolan McLean","Brock Wilken","Welbyn Francisca","Tyler Locklear","Jonah Tong","Juan Brito","Theo Gillen","Michael McGreevey","Caleb Durbin","Trevor Harrison","George Klassen","Troy Melton","Seaver King","Slade Caldwell","Grant Taylor","Zach Dezenzo","Trey Yesavage","Yophery Rodriguez","Drew Gilbert","Robbie Snelling","Ricky Tiedemann","Jedixson Paez","Deyvison De Los Santos","Chase Hampton","Hurston Waldrep","Cam Caminiti","Yoeilin Cespedes","Moises Chace","Edgardo Henriquez","Jacob Melton","Jurrangelo Cjintje","Tai Peete","Luke Adams","Jesus Baez","Brailer Guerrero","Carson Whisenhunt","Ty Johnson","Gary Gill Hill","Ramon Ramirez","Zac Veen","Tommy Troy","Druw Jones","Kellon Lindsey","Brandon Winokur","Thomas Saggese","Max Muncy","Sammy Stafura","Charlee Soto"]
        for n in names:
            try:
                obj = models.Player.objects.get(name=n)
                print(f"{n},,{obj.fg_id},{obj.mlbam_id}")
            except:
                print(f"{n},,,")