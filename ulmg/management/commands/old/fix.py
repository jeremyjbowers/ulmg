import json
import time
import csv

from bs4 import BeautifulSoup
from django.core.management.base import BaseCommand, CommandError
import requests

from ulmg import models, utils


class Command(BaseCommand):
    def handle(self, *args, **options):
        url = "https://www.baseballamerica.com/umbraco/surface/list/loadmorelistitemsajax?startPage=1&pageId=92557&showAllItems=true&filterModel.position=&filterModel.keyword="

        r = requests.get(url)
        soup = BeautifulSoup(r.content, 'lxml')
        prospects = soup.select('li.list-individual-rank-item')

        players = []
        players_by_team = {}

        for p in prospects:
            player_dict = {}
            player_dict['name'] = p.select('div.player-details h3')[0].text.strip()
            player_dict['rank'] = int(p.select('div.current-ranking')[0].text.strip())
            player_dict['team'] = p.select('div.team-position-container span')[0].text.strip()
            player_dict['ulmg'] = ""


            obj = utils.fuzzy_find_player(player_dict["name"], score=0.7)
            
            if obj and len(obj) > 0:
                obj = obj[0]

            team = 'Unowned'
            player_dict['ulmg'] = team

            if player_dict['name'] == "Alex Ramirez":
                team = "ABQ"

            if player_dict['name'] == "Logan Allen":
                team = "AKS"

            if player_dict['name'] == "D.L. Hall":
                team = "DET"

            if obj:
                if obj.is_owned:
                    team = obj.team.abbreviation

            if not players_by_team.get(team, None):
                players_by_team[team] = {"count": 0, "score": 0, "ranks": [], "players": []}

            players_by_team[team]['count'] += 1
            players_by_team[team]['score'] += 101 - player_dict['rank']
            players_by_team[team]['ranks'].append(player_dict['rank'])
            players_by_team[team]['players'].append(f"{player_dict['name']} ({player_dict['rank']})")

            players.append(player_dict)
            slack_string = f"{player_dict['rank']}. {player_dict['name']}"
            if team != "Unowned":
                slack_string += f" ({team})"

            print(slack_string)

        team_prospects = [(team, data) for team, data in players_by_team.items()]
        team_prospects = sorted(team_prospects, key=lambda x:x[1]['score'], reverse=True)

        for team, data in team_prospects:
            team_string = f" # *{team}*: {data['score']} points, {data['count']} ranked players: "
            player_string = ", ".join(data['players'])
            print(team_string + player_string)

        # draft = []

        # with open("data/2022/ftrax_2022_draft.html", "r") as readfile:
        #     soup = BeautifulSoup(readfile.read(), "html.parser")
        #     rows = soup.select("table.draftGrid tr")[1:]

        #     for rnd, row in enumerate(rows):
        #         rnd = rnd + 1

        #         for pick, cell in enumerate(row.select("td")[1:]):
        #             pick = pick + 1
        #             name = cell.select("a")[0].text.strip()
        #             team = cell.select("div > div")[0].text.split(" (")[0].strip()
        #             pos = (
        #                 cell.select("div > div")[0]
        #                 .text.split(" (")[1]
        #                 .split(")")[0]
        #                 .strip()
        #             )

        #             payload = {
        #                 "pick": pick,
        #                 "round": rnd,
        #                 "player": name,
        #                 "team": team,
        #                 "position": pos,
        #             }
        #             draft.append(payload)

        # with open("data/2022/ftrax_2022_draft.json", "w") as writefile:
        #     writefile.write(json.dumps(draft))

        # with open("data/2022/ftrax_2022_draft.csv", "w") as writefile:
        #     fieldnames = draft[0].keys()
        #     writer = csv.DictWriter(writefile, fieldnames=fieldnames)
        #     writer.writeheader()

        #     for pick in draft:
        #         writer.writerow(pick)
