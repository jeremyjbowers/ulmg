import json

import requests
from bs4 import BeautifulSoup


def main():
    url = "https://www.fantraxhq.com/top-fantasy-baseball-prospects/"
    r = requests.get(url)
    soup = BeautifulSoup(r.text, "lxml")
    rows = soup.select("table.tablepress tbody tr")
    player_headers = ["rk", "name", "pos", "age"]
    players = []

    for row in rows:
        cells = [c.text for c in row.select("td")]
        player = dict(zip(player_headers, cells))
        players.append(player)

    with open("ftx.json", "w") as writefile:
        writefile.write(json.dumps(players))


if __name__ == "__main__":
    main()
