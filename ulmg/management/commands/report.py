import csv
import requests
from bs4 import BeautifulSoup

from django.core.management.base import BaseCommand, CommandError

from ulmg import models


class Command(BaseCommand):
    def handle(self, *args, **kwargs):
        teams = {}
        teams['unowned'] = []
        for t in models.Team.objects.all():
            teams[t.abbreviation] = []

        busted_players = {
            "Juan Soto": "CHI",
            "Fernando Tatis Jr.": "CHI",
            "Julio Rodriguez": "LOU",
            "Jose Ramirez": "LNG",
            "Michael Harris II": "ABQ",
            "Pete Alonso": "PIT",
            "Jazz Chisholm Jr.": "CLE",
            "Luis Robert Jr.": "CHI",
            "Luis Garcia Jr.": "DET",
            "Mason Miller": "NYH",
            "Jared Jones": "ABQ",
            "Logan O’Hoppe": "CHI",
            "Jeremy Pena": "AKS",
            "Jacob Wilson": "CAR",
            "Luis Castillo": "LOU",
            "Tyler O’Neill": "ATL",
            "Edwin Diaz": "ATL",
            "Jung Hoo Lee": "PEN",
            "Nick Castellanos": "CAR",
            "JJ Bleday": "CIN",
            "Luis Pena": 'unowned',
            "Ryan O’Hearn": "ADK",
            "Pete Fairbanks": "CHI",
            "Tre’ Morgan": "ABQ",
            "Ke’Bryan Hayes": "AKS",
            "Cade Smith": "ATL",
            "Luis L. Ortiz": "WCH",
            "Will Smith": "WCH",
            "Josh Smith": "CAR",
        }

        r = requests.get('https://www.baseballamerica.com/stories/top-500-fantasy-baseball-dynasty-rankings-for-2025/')
        soup = BeautifulSoup(r.content, features="html5lib")
        players = soup.select('.wp-block-table table tbody tr')
        for p in players:
            cells = p.select('td')
            rank = int(cells[0].text.strip())
            player = cells[1].text.strip()
            position = cells[2].text.strip()
            team = cells[3].text.strip()
            change = cells[5].text.strip()
            points = (500-rank)+1

            player_dict = {
                "rank": rank,
                "name": player,
                "position": position,
                "mlb_team": team,
                "change": change,
                "ulmg_team": None,
                "points": points,
            }

            if busted_players.get(player):
                player_dict['ulmg_team'] = busted_players.get(player)
                teams[player_dict['ulmg_team']].append(player_dict)

            else:          
                try:
                    obj = models.Player.objects.get(name=player)
                    if not obj.team:
                        player_dict['ulmg_team'] = "unowned"
                    else:
                        player_dict['ulmg_team'] = obj.team.abbreviation
                    teams[player_dict['ulmg_team']].append(player_dict)
                except:
                    print(player)


        for team, players in teams.items():
            team_points = 0
            for p in players:
                team_points += p['points']
            print(team, team_points)

        for p in teams['unowned']:
            print(p)
    # def handle(self, *args, **options):
    #     players = []
    #     for team in models.Team.objects.all():
    #         players += [
    #             p
    #             for p in models.Player.objects.filter(team=team).values(
    #                 "name", "team__abbreviation", "level"
    #             )
    #         ]

    #     with open("for_rus.csv", "w") as writefile:
    #         fieldnames = players[0].keys()
    #         writer = csv.DictWriter(writefile, fieldnames)

    #         writer.writeheader()
    #         for player in players:
    #             writer.writerow(player)
