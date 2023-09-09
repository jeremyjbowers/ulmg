import re, os

import boto3
from django.core.management.base import BaseCommand, CommandError

from ulmg import models, utils


"""
[1]BOXSCORE: 2022 Atlanta Crackers At 2022 Anaheim Scuppers            4/14/2022

[1]  Crackers           AB  R  H RBI AVG     Scuppers           AB  R  H RBI AVG
  T.Grisham CF        3  1  0  0 .000     T.Turner 2B         5  0  0  0 .133
  J.Polanco 2B        5  1  1  0 .500     M.Machado 3B        4  0  1  1 .267
  C.Yelich RF         3  2  1  3 .273     J.Walsh RF          4  0  1  0 .200
D-N.Cruz PH           1  0  0  0 .200     K.Tucker LF         4  0  0  0 .176
E-B.Nimmo RF          0  0  0  0 .273     E.Hosmer 1B         4  0  3  0 .500
  T.O'Neill LF        4  1  2  3 .313     S.Perez C           3  1  0  0 .200
  J.Votto 1B          2  0  0  0 .333     A.Verdugo CF        4  1  1  0 .143
C-A.Vaughn 3B         2  1  1  0 .500     T.Stephenson DH     0  0  0  0 .167
  N.Arenado 3B        2  0  1  0 .154   A-R.Mountcastle PR,DH 3  1  1  0 .125
B-J.Aguilar PR,1B     0  1  0  0 .100     N.Lopez SS          4  0  2  2 .429
  A.Pollock DH        4  0  0  0 .250
  J.Cronenworth SS    4  0  1  2 .143
  W.Contreras C       4  2  1  0 .143
                     -- -- -- ---                            -- -- -- ---
[1]         Totals      34  9  8  8                 Totals      35  3  9  3

A-Pinch Ran For Stephenson In 3rd Inning
B-Pinch Ran For Arenado In 6th Inning
C-Subbed Defensively (3B) For Votto In 6th Inning
D-Pinch Hit For Yelich In 8th Inning
E-Subbed Defensively (RF) For Cruz In 8th Inning

INJURY: Tyler Stephenson INJURED (for 5 more games) in 3rd inning
INJURY: Joey Votto INJURED (for 0 more games) in 6th inning
INJURY: Nolan Arenado INJURED (for 3 more games) in 6th inning

Crackers........ 0 0 3  0 0 0  3 1 2  -  9  8  0
Scuppers........ 0 0 1  0 0 0  2 0 0  -  3  9  1

[1]Crackers (3-1)           IP       H   R  ER  BB  SO  HR    ERA
P.Lopez WIN(1-0)          6       6   3   3   0   7   0   4.50
S.Lugo                    2       2   0   0   0   5   0   0.00
L.Hendriks                1       1   0   0   0   2   0   4.50
[1]Totals                    9       9   3   3   0  14   0

[1]Scuppers (1-3)           IP       H   R  ER  BB  SO  HR    ERA
L.Garcia LOSS(0-1)        6       4   6   6   7   5   2   9.00
A.Chapman                 2       1   1   0   2   3   0   0.00
M.Melancon                1       3   2   2   1   0   0  18.00
[1]Totals                    9       8   9   8  10   8   2

ATTENDANCE- 15,507 DATE- Thursday, April 14th 2022 TIME- Day WEATHER- Bad
UMPIRES- Hunter Wendelstedt, Larry Young, Charlie Reliford, Mike Everitt
T- 3:00
LEFT ON BASE- Crackers: 9  Scuppers: 7
DOUBLE PLAYS- Crackers: 1  Scuppers: 1
ERRORS- J.Walsh
DOUBLES- J.Polanco(3rd), M.Machado(1st), E.Hosmer(2nd), A.Verdugo(1st),
         R.Mountcastle(1st)
HOME RUNS- C.Yelich(1st), T.O'Neill(3rd)
RBIs- C.Yelich-3(3rd), T.O'Neill-3(7th), J.Cronenworth-2(2nd), M.Machado(2nd),
      N.Lopez-2(2nd)
WALKS- T.Grisham-2, C.Yelich, T.O'Neill, J.Votto, J.Aguilar-2, A.Pollock,
       J.Cronenworth, W.Contreras
HIT BY PITCH- N.Arenado, S.Perez, T.Stephenson
STRIKE OUTS- T.Grisham, C.Yelich, N.Cruz, T.O'Neill, N.Arenado, A.Pollock,
             W.Contreras-2, T.Turner-4, M.Machado, J.Walsh-2, K.Tucker-3,
             S.Perez, A.Verdugo, R.Mountcastle, N.Lopez
GIDP- A.Pollock, S.Perez
WILD PITCHES- L.Garcia-4, A.Chapman
2-out RBI- T.O'Neill-3, M.Machado, J.Cronenworth-2
RLISP 2-out- J.Cronenworth, N.Arenado, J.Walsh, A.Verdugo, M.Machado,
             W.Contreras-2, N.Cruz
TEAM RISP- Crackers: 3 for 12  Scuppers: 1 for 8
WEB GEMS- Top 9th: Trea Turner robbed A.J. Pollock of a base hit.

The Atlanta Crackers had very little trouble at Angels Stadium downing the
Anaheim Scuppers.  The score was 9 to 3.

Pablo Lopez(1-0) delivered a fine performance for Atlanta.  He went 6 innings
and surrended up 6 hits and no walks.  Lopez whiffed an impressive total of 7
Anaheim batters.  Atlanta rapped out 8 hits for the afternoon.

Luis Garcia(0-1) was the loser.  He pitched 6 innings allowing 4 hits and 7
walks.
"""


class Command(BaseCommand):
    def handle(self, *args, **options):
        year = utils.get_current_season()
        bucket = "static-theulmg"
        prefix = f"strat-data/{year}/"

        session = boto3.session.Session()
        client = session.client(
            "s3",
            region_name="nyc3",
            endpoint_url="https://nyc3.digitaloceanspaces.com",
            aws_access_key_id=os.environ.get("DO_ACCESS_KEY_ID", None),
            aws_secret_access_key=os.environ.get("DO_SECRET_ACCESS_KEY", None),
        )

        def get_all_s3_objects(s3, **base_kwargs):
            continuation_token = None
            while True:
                list_kwargs = dict(MaxKeys=1000, **base_kwargs)
                if continuation_token:
                    list_kwargs["ContinuationToken"] = continuation_token

                response = s3.list_objects_v2(**list_kwargs)
                yield from response.get("Contents", [])

                if not response.get("IsTruncated"):  # At the end of the list?
                    break
                continuation_token = response.get("NextContinuationToken")

        box_score_keys = [
            k["Key"]
            for k in get_all_s3_objects(client, Bucket=bucket, Prefix=prefix)
            if ".prt" and "BOX" in k["Key"]
        ]

        def parse_box_file(box_file):
            game_data = {
                "game_date": None,
                "home_team": None,
                "home_team_mascot": None,
                "away_team_mascot": None,
                "away_team": None,
                "home_team_score": None,
                "away_team_score": None,
                "winning_team": None,
                "player_stats": [],
            }

            for line in box_file.split("\n"):
                try:
                    # Get teams, game date
                    # this is usually like the 1st or second line in the file.
                    # we could get teams further down but this makes matching easier
                    if "BOXSCORE:" in line:
                        line = line.replace("[1]BOXSCORE: ", "")
                        away_team = (
                            line.split(" At ")[0].replace(f"{year} ", "").strip()
                        )
                        home_team = (
                            line.split(" At ")[1].replace(f"{year} ", "").strip()
                        )
                        date_string = None

                        away_team_mascot = away_team.split(" ")[-1].strip()

                        regex = r"[\s]{2,}([0-9]{1,}/[[0-9]{1,2}/[0-9]{4})"
                        matches = re.finditer(regex, home_team, re.MULTILINE)
                        for match in matches:
                            for group in match.groups():
                                date_string = group.strip()

                            home_team = home_team.replace(date_string, "").strip()
                            home_team_mascot = home_team.split(" ")[-1].strip()

                            game_data["game_date"] = date_string
                            game_data["home_team"] = home_team
                            game_data["away_team"] = away_team
                            game_data["home_team_mascot"] = home_team_mascot
                            game_data["away_team_mascot"] = away_team_mascot

                    # Get line score
                    # Give score to the correct team
                    if "-" and "." in line:
                        line_mascot = line.split(".")[0].strip()
                        if line_mascot == game_data["home_team_mascot"]:
                            game_data["home_team_score"] = int(
                                line.split("-")[1].strip().split(" ")[0].strip()
                            )

                        if line_mascot == game_data["away_team_mascot"]:
                            game_data["away_team_score"] = int(
                                line.split("-")[1].strip().split(" ")[0].strip()
                            )
                except:
                    pass

            # Determine the winner
<<<<<<< Updated upstream
            if game_data["home_team_score"] and game_data["away_team_score"]:
                if game_data["home_team_score"] > game_data["away_team_score"]:
                    game_data["winning_team"] = game_data["home_team"]

                if game_data["away_team_score"] > game_data["home_team_score"]:
                    game_data["winning_team"] = game_data["away_team"]
=======
            if game_data['home_team_score'] != None and game_data['away_team_score'] != None:
                if game_data['home_team_score'] > game_data['away_team_score']:
                    game_data['winning_team'] = game_data['home_team']
>>>>>>> Stashed changes

            return game_data

        for k in box_score_keys:
            file_data = client.get_object(Bucket=bucket, Key=k)
<<<<<<< Updated upstream
            game_data = parse_box_file(file_data["Body"].read().decode())
            print(game_data)
=======
            game_data = parse_box_file(file_data['Body'].read().decode())

            print(game_data['winning_team'])
>>>>>>> Stashed changes
