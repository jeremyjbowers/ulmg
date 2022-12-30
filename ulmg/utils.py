import csv
import pickle
import os.path
import platform
import sys
from decimal import Decimal
from datetime import datetime

from bs4 import BeautifulSoup
from dateutil.parser import parse
from django.apps import apps
from django.db import connection
from django.db.models import Avg, Sum, Count
from django.contrib.postgres.search import TrigramSimilarity
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from googleapiclient.discovery import build
from google.oauth2 import service_account
import requests
import ujson as json
import time

from ulmg import models


def get_fg_birthdate(player):
    if player.fg_id and not player.birthdate:
        player_url = f"https://www.fangraphs.com/statss.aspx?playerid={player.fg_id}"
        r = requests.get(player_url)
        soup = BeautifulSoup(r.content)
        date_cell = soup.select('tr.player-info__bio-birthdate td')[0].text

        try:
            player.birthdate = parse(date_cell.split('(')[0].strip())
            player.save()
            print(player.name, player.birthdate, player_url)
        
        except:
            print(player.name, player_url, date_cell.split('(')[0].strip())

        time.sleep(1.5)


def get_ulmg_season(date):
    if date.month >= 11:
        return int(date.year) + 1
    return date.year


def get_current_season():
    season = settings.CURRENT_SEASON
    if settings.CURRENT_SEASON_TYPE == "offseason":
        season = season - 1
    return season


def get_strat_season():
    today = datetime.today()
    return get_ulmg_season(today) - 1


def to_int(might_int, default=None):
    if type(might_int) is int:
        return might_int

    if type(might_int) is str:
        try:
            return int(might_int.strip().replace("\xa0", ""))
        except:
            pass

    try:
        return int(might_int)
    except:
        pass

    if default:
        return default

    return None


def to_float(might_float, default=None):
    try:
        return float(might_float)
    except:
        pass

    return default


def reset_player_stats(id_type=None, player_ids=None):
    if id_type and player_ids:
        lookup = f"{id_type}__in"
        keyword = player_ids
        models.Player.objects.filter(**{lookup: keyword}).update(stats=None)

    else:
        models.Player.objects.filter(stats__isnull=False).update(stats=None)


def get_scriptname():
    return " ".join(sys.argv)


def get_hostname():
    return platform.node()


def generate_timestamp():
    return int(datetime.now().timestamp())


def send_email(from_email=None, to_emails=[], text=None, subject=None):
    if from_email and len(to_emails) > 0:
        return requests.post(
            "https://api.mailgun.net/v3/mail.theulmg.com/messages",
            auth=("api", settings.MAILGUN_API_KEY),
            data={
                "from": from_email,
                "to": to_emails,
                "subject": subject,
                "text": text,
            },
        )
    return None


def fuzzy_find_prospectrating(
    name_fragment, score=0.7, position=None, mlb_team_abbr=None
):

    output = []

    players = models.Player.objects

    if position:
        players = players.filter(position=position)

    if mlb_team_abbr:
        players = players.filter(mlb_team_abbr=mlb_team_abbr)

    players = players.annotate(similarity=TrigramSimilarity("name", name_fragment))
    players = players.filter(similarity__gt=score)
    players = players.order_by("-similarity")

    for p in players:
        try:
            obj = models.ProspectRating.objects.get(player=p)
            output.append(obj)
        except models.ProspectRating.DoesNotExist:
            pass

    return output


def strat_find_player(
    first_initial, last_name, hitter=True, mlb_team_abbr=None, ulmg_id=None
):
    if ulmg_id:
        return models.Player.objects.filter(id=ulmg_id)[0]

    players = models.Player.objects.filter(is_carded=True)

    if hitter:
        players = players.exclude(position="P")

    else:
        players = players.filter(position="P")

    players = players.filter(first_name__startswith=first_initial)

    players = players.annotate(similarity=TrigramSimilarity("last_name", last_name))
    players = players.filter(similarity__gt=0.5)
    players = players.order_by("-similarity")

    if len(players) > 1:
        if mlb_team_abbr:
            players = players.filter(mlb_team_abbr=mlb_team_abbr)

    if len(players) == 0:
        return None

    return players[0]


def fuzzy_find_player(name_fragment, score=0.7, position=None, mlb_team_abbr=None):

    players = models.Player.objects

    if position:
        players = players.filter(position=position)

    if mlb_team_abbr:
        players = players.filter(mlb_team_abbr=mlb_team_abbr)

    players = players.annotate(similarity=TrigramSimilarity("name", name_fragment))
    players = players.filter(similarity__gt=score)
    players = players.order_by("-similarity")

    return players


def update_wishlist(playerid, wishlist, rank, tier, remove=False):
    p = models.Player.objects.get(id=playerid)
    w, created = models.WishlistPlayer.objects.get_or_create(
        player=p, wishlist=wishlist
    )

    if remove:
        player_name = str(w.player.name)
        w.delete()
        return player_name

    else:
        if tier:
            w.tier = tier

        if rank:
            w.rank = rank

        if tier or rank:
            w.save()

        return w.player.name


def parse_fg_fv(raw_fv_str):
    if raw_fv_str == "":
        return None

    if "+" in raw_fv_str:
        return Decimal(f"{raw_fv_str.split('+')[0]}.5")

    try:
        return Decimal(f"{raw_fv_str}")

    except:
        return None


def build_context(request):
    context = {}

    # to build the nav
    context["teamnav"] = models.Team.objects.all().values("abbreviation")
    context["draftnav"] = settings.DRAFTS
    context["mlb_roster_size"] = settings.MLB_ROSTER_SIZE
    context["roster_tab"] = settings.TEAM_ROSTER_TAB
    context["protect_tab"] = settings.TEAM_PROTECT_TAB
    context["live_tab"] = settings.TEAM_LIVE_TAB

    # for search
    queries_without_page = dict(request.GET)
    if queries_without_page.get("page", None):
        del queries_without_page["page"]
    context["q_string"] = "&".join(
        ["%s=%s" % (k, v[-1]) for k, v in queries_without_page.items()]
    )

    # add the owner to the page
    context["owner"] = None
    if request.user.is_authenticated:
        owner = models.Owner.objects.get(user=request.user)
        context["owner"] = owner

    return context


def write_csv(path, payload):
    with open(path, "w") as csvfile:
        fieldnames = list(payload[0].keys())
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for p in payload:
            writer.writerow(p)


# covered
def normalize_pos(pos):
    """
    Normalize positions to P, C, IF, OF or IF/OF
    """
    # Any pitcher.
    if "P" in pos.upper():
        return "P"

    # Catcher-only.
    if pos.upper() == "C":
        return "C"

    # One of the IF positions.
    if pos.upper() in ["1B", "2B", "3B", "SS"]:
        return "IF"

    # One of the OF positions.
    if pos.upper() in ["RF", "CF", "LF"]:
        return "OF"

    # Catch folks who are more than one OF and maybe some IF.
    if "F" in pos.upper():
        if "B" in pos.upper() or "SS" in pos.upper():
            return "IF-OF"
        return "OF"

    # If you're left, you're a mix of IF.
    if "B" in pos.upper() or "SS" in pos.upper():
        return "IF"

    # Die if we cannot get a position.
    # This will likely fail to save, as positions are required?
    return None


# covered
def str_to_bool(possible_bool):
    if isinstance(possible_bool, str):
        if possible_bool.lower() in ["y", "yes", "t", "true"]:
            return True
        if possible_bool.lower() in ["n", "no", "f", "false"]:
            return False
    return None


def int_or_none(possible_int):
    if isinstance(possible_int, int):
        return possible_int
    try:
        return to_int(possible_int)
    except:
        pass
    return None


def is_even(possible_int):
    possible_int = int_or_none(possible_int)
    if possible_int:
        if possible_int == 0:
            return True
        if possible_int % 2 == 0:
            return True
    return False


def get_sheet(sheet_id, sheet_range):
    SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]

    creds = service_account.Credentials.from_service_account_file(
        "credentials.json", scopes=SCOPES
    )
    service = build("sheets", "v4", credentials=creds)
    sheet = service.spreadsheets()

    result = sheet.values().get(spreadsheetId=sheet_id, range=sheet_range).execute()
    values = result.get("values", None)

    if values:
        return [dict(zip(values[0], r)) for r in values[1:]]
    return []


def get_fg_results(url):
    r = requests.get(url, verify=False)
    soup = BeautifulSoup(r.text, "html.parser")
    return soup.select("#LeaderBoard1_dg1_ctl00 tbody tr")


def get_fg_minor_season(season=None, timestamp=None, scriptname=None, hostname=None):

    if not hostname:
        hostname = get_hostname()

    if not scriptname:
        scriptname = get_scriptname()

    if not timestamp:
        timestamp = generate_timestamp()

    if not season:
        season = get_current_season()

    print(f"{timestamp}\t{season}\tget_fg_minor_season")

    headers = {"accept": "application/json"}

    players = {"bat": [], "pit": []}

    for k, v in players.items():
        url = f"https://www.fangraphs.com/api/leaders/minor-league/data?pos=all&level=0&lg=2,4,5,6,7,8,9,10,11,14,12,13,15,16,17,18,30,32,33&stats={k}&qual=0&type=0&team=&season={season}&seasonEnd={season}&org=&ind=0&splitTeam=false"

        print(url)
        r = requests.get(url, verify=False)
        players[k] += r.json()

    for k, v in players.items():
        for player in v:
            fg_id = player["playerids"]
            name = player["PlayerName"]
            p = models.Player.objects.filter(fg_id=fg_id)

            if len(p) == 1:
                obj = p[0]

                stats_dict = {}
                stats_dict["type"] = "minors"
                stats_dict["timestamp"] = timestamp
                stats_dict["level"] = player["aLevel"]
                stats_dict["script"] = scriptname
                stats_dict["host"] = hostname
                stats_dict["year"] = season
                stats_dict["slug"] = f"{stats_dict['year']}_{stats_dict['type']}"

                if k == "bat":
                    stats_dict["side"] = "hit"
                    stats_dict["hits"] = to_int(player["H"])
                    stats_dict["2b"] = to_int(player["2B"])
                    stats_dict["3b"] = to_int(player["3B"])
                    stats_dict["hr"] = to_int(player["HR"])
                    stats_dict["sb"] = to_int(player["SB"])
                    stats_dict["runs"] = to_int(player["R"])
                    stats_dict["rbi"] = to_int(player["RBI"])
                    stats_dict["avg"] = to_float(player["AVG"])
                    stats_dict["obp"] = to_float(player["OBP"])
                    stats_dict["slg"] = to_float(player["SLG"])
                    stats_dict["babip"] = to_float(player["BABIP"])
                    stats_dict["wrc_plus"] = to_int(player["wRC+"])
                    stats_dict["plate_appearances"] = to_int(player["PA"])
                    stats_dict["iso"] = to_float(player["ISO"])
                    stats_dict["k_pct"] = to_float(player["K%"], default=0.0) * 100.0
                    stats_dict["bb_pct"] = to_float(player["BB%"], default=0.0) * 100.0
                    stats_dict["woba"] = to_float(player["wOBA"])

                if k == "pit":
                    stats_dict["side"] = "pitch"
                    stats_dict["g"] = to_int(player["G"])
                    stats_dict["gs"] = to_int(player["GS"])
                    stats_dict["k"] = to_int(player["SO"])
                    stats_dict["bb"] = to_int(player["BB"])
                    stats_dict["ha"] = to_int(player["H"])
                    stats_dict["hra"] = to_int(player["HR"])
                    stats_dict["ip"] = to_float(player["IP"])
                    stats_dict["k_9"] = to_float(player["K/9"])
                    stats_dict["bb_9"] = to_float(player["BB/9"])
                    stats_dict["hr_9"] = to_float(player["HR/9"])
                    stats_dict["lob_pct"] = (
                        to_float(player["LOB%"], default=0.0) * 100.0
                    )
                    stats_dict["gb_pct"] = to_float(player["GB%"], default=0.0) * 100.0
                    stats_dict["hr_fb"] = to_float(player["HR/FB"])
                    stats_dict["era"] = to_float(player["ERA"])
                    stats_dict["fip"] = to_float(player["FIP"])
                    stats_dict["xfip"] = to_float(player["xFIP"])

                obj.set_stats(stats_dict)
                obj.save()

                current_dict = stats_dict.copy()
                current_dict["slug"] = "current"

                obj.set_stats(current_dict)
                obj.save()


def get_fg_roster_files():
    teams = settings.ROSTER_TEAM_IDS

    for team_id, team_abbrev, team_name in teams:

        url = f"https://cdn.fangraphs.com/api/depth-charts/roster?teamid={team_id}"
        roster = requests.get(url, verify=False).json()

        with open(f"data/rosters/{team_abbrev}_roster.json", "w") as writefile:
            writefile.write(json.dumps(roster))


def import_players_from_rosters():
    teams = settings.ROSTER_TEAM_IDS

    for team_id, team_abbrev, team_name in teams:

        with open(f"data/rosters/{team_abbrev}_roster.json", "r") as readfile:

            roster = json.loads(readfile.read())

            for player in roster:

                obj = None

                fg_id = None

                if player.get("playerid"):
                    fg_id = player["playerid"]

                if player.get("playerid1") and not fg_id:
                    fg_id = player["playerid1"]

                if player.get("playerid2") and not fg_id:
                    fg_id = player["playerid2"]

                if player.get("oPlayerId") and not fg_id:
                    fg_id = player["oPlayerId"]

                # player has an fg_id but missing other IDs
                if fg_id:
                    obj = models.Player.objects.filter(fg_id=fg_id)

                    if len(obj) == 1:
                        obj = obj[0]

                        if player.get("mlbamid", None):
                            obj.mlbam_id = player["mlbamid"]

                        obj.save()

                        continue

                # player has a minormasterid in the fg_id and needs updating
                if player.get("minormasterid", None) and fg_id:
                    obj = models.Player.objects.filter(fg_id=player["minormasterid"])

                    if len(obj) == 1:
                        obj = obj[0]

                        obj.fg_id = fg_id

                        if player.get("mlbamid", None):
                            obj.mlbam_id = player["mlbamid"]

                        obj.save()

                        continue

                # player has no fg_id, but we found one with a name match
                pos = normalize_pos(player["position"])
                obj = fuzzy_find_player(player["player"], score=0.7)
                if len(obj) == 1:
                    obj = obj[0]

                    if not obj.fg_id:
                        if player.get("minormasterid"):
                            obj.fg_id = player["minormasterid"]

                        if fg_id:
                            obj.fg_id = fg_id

                        if player.get("mlbamid"):
                            obj.mlbam_id = player["mlbamid"]

                        obj.save()

                # we cannot find this name in our db
                elif len(obj) == 0:
                    age = None
                    try:
                        age = int(player["age"].split(".")[0])
                    except:
                        pass

                    obj = models.Player(
                        name=player["player"],
                        position=pos,
                        level="B",
                        raw_age=age,
                        mlb_team_abbr=team_abbrev,
                    )

                    if player.get("minormasterid"):
                        obj.fg_id = player["minormasterid"]

                    if fg_id:
                        obj.fg_id = fg_id

                    if player.get("mlbamid"):
                        obj.mlbam_id = player["mlbamid"]

                    if not obj.fg_id:
                        pass
                        # print(f'~ {obj}')

                    else:
                        print(f"+ {obj}")
                        obj.save()

                # there are two or more players with this name
                elif len(obj) > 1:
                    print(f"2x {obj}")


def parse_roster_info():

    teams = settings.ROSTER_TEAM_IDS
    for team_id, team_abbrev, team_name in teams:
        with open(f"data/rosters/{team_abbrev}_roster.json", "r") as readfile:
            roster = json.loads(readfile.read())
            for player in roster:
                p = None
                try:
                    try:
                        p = models.Player.objects.get(fg_id=player["playerid1"])
                    except:
                        try:
                            p = models.Player.objects.get(fg_id=player["minormasterid"])
                        except:
                            pass

                    if p:
                        if player.get("mlevel", None):
                            p.role = player["mlevel"]
                        elif player.get("role", None):
                            if player["role"] != "":
                                p.role = player["role"]

                        if p.role == "MLB":
                            p.ls_is_mlb = True
                            p.is_mlb = True

                        if "pp" in player["type"]:
                            p.is_player_pool = True

                        if player["type"] == "mlb-tx-pp":
                            p.is_player_pool = True

                        if player["type"] == "mlb-tx-pt":
                            p.is_player_pool = True

                        if player["type"] == "mlb-bp":
                            p.is_bullpen = True

                        if player["type"] == "mlb-sp":
                            p.is_starter = True

                        if player["type"] == "mlb-bn":
                            p.is_bench = True

                        if player["type"] == "mlb-sl":
                            p.is_starter = True

                        if "il" in player["type"]:
                            p.is_injured = True

                        p.injury_description = player.get("injurynotes", None)
                        p.mlbam_id = player.get("mlbamid1", None)
                        p.mlb_team = team_name
                        p.mlb_team_abbr = team_abbrev

                        if player["roster40"] == "Y":
                            p.is_mlb40man = True

                        p.save()

                except Exception as e:
                    prto_int(f"error loading {player['player']}: {e}")


def get_fg_major_hitter_season(
    season=None, timestamp=None, scriptname=None, hostname=None
):

    if not hostname:
        hostname = get_hostname()

    if not scriptname:
        scriptname = get_scriptname()

    if not timestamp:
        timestamp = generate_timestamp()

    if not season:
        season = get_current_season()

    print(f"{timestamp}\t{season}\tget_fg_major_hitter_season")

    url = f"https://www.fangraphs.com/leaders.aspx?pos=all&stats=bat&lg=all&qual=0&type=c,6,-1,312,305,309,306,307,308,310,311,-1,23,315,-1,38,316,-1,50,317,7,8,9,10,11,12,13,14,21,23,34,35,37,38,39,40,41,50,52,57,58,61,62,5&season={season}&month=0&season1={season}&ind=0&team=0&rost=0&age=0&filter=&players=0&startdate={season}-01-01&enddate={season}-12-31&sort=3,d&page=1_5000"

    rows = get_fg_results(url)

    for row in rows:
        h = row.select("td")
        stats_dict = {}

        stats_dict["year"] = season
        stats_dict["type"] = "majors"
        stats_dict["timestamp"] = timestamp
        stats_dict["level"] = "mlb"
        stats_dict["side"] = "hit"
        stats_dict["script"] = scriptname
        stats_dict["host"] = hostname
        stats_dict["slug"] = f"{stats_dict['year']}_{stats_dict['type']}"

        obj = models.Player.objects.filter(
            fg_id=h[1].select("a")[0].attrs["href"].split("playerid=")[1].split("&")[0]
        )

        if obj.count() > 0:
            obj = obj[0]

            stats_dict["hits"] = to_int(h[18].text)
            stats_dict["2b"] = to_int(h[20].text)
            stats_dict["3b"] = to_int(h[21].text)
            stats_dict["hr"] = to_int(h[22].text)
            stats_dict["sb"] = to_int(h[26].text)
            stats_dict["runs"] = to_int(h[23].text)
            stats_dict["rbi"] = to_int(h[24].text)
            stats_dict["wrc_plus"] = to_int(h[39].text)
            stats_dict["plate_appearances"] = to_int(h[3].text)
            stats_dict["ab"] = to_int(h[41].text)

            stats_dict["avg"] = to_float(h[12].text)
            stats_dict["xavg"] = to_float(h[13].text)
            stats_dict["obp"] = to_float(h[30].text)
            stats_dict["slg"] = to_float(h[14].text)
            stats_dict["xslg"] = to_float(h[15].text)
            stats_dict["babip"] = to_float(h[34].text)
            stats_dict["iso"] = to_float(h[33].text)
            stats_dict["k_pct"] = to_float(h[29].text.replace("%", ""))
            stats_dict["bb_pct"] = to_float(h[28].text.replace("%", ""))
            stats_dict["xwoba"] = to_float(h[17].text)

            obj.set_stats(stats_dict)
            obj.save()

            current_dict = stats_dict.copy()
            current_dict["slug"] = "current"

            obj.set_stats(current_dict)
            obj.save()


def get_fg_major_pitcher_season(
    season=None, timestamp=None, scriptname=None, hostname=None
):

    if not hostname:
        hostname = get_hostname()

    if not scriptname:
        scriptname = get_scriptname()

    if not timestamp:
        timestamp = generate_timestamp()

    if not season:
        season = get_current_season()

    print(f"{timestamp}\t{season}\tget_fg_major_pitcher_season")

    url = f"https://www.fangraphs.com/leaders.aspx?pos=all&stats=pit&lg=all&qual=2&type=c,4,5,11,7,8,13,-1,24,19,15,18,36,37,40,43,44,48,51,-1,240,-1,6,332,45,62,122,-1,59,17,301,302,303,117,118,119&season={season}&month=0&season1={season}&ind=0&team=0&rost=0&age=0&filter=&players=0&startdate={season}-01-01&enddate={season}-12-31&sort=8,d&page=1_5000"

    rows = get_fg_results(url)

    for row in rows:
        h = row.select("td")
        stats_dict = {}

        stats_dict["year"] = season
        stats_dict["type"] = "majors"
        stats_dict["timestamp"] = timestamp
        stats_dict["level"] = "mlb"
        stats_dict["side"] = "pitch"
        stats_dict["script"] = scriptname
        stats_dict["host"] = hostname
        stats_dict["slug"] = f"{stats_dict['year']}_{stats_dict['type']}"

        obj = models.Player.objects.filter(
            fg_id=h[1].select("a")[0].attrs["href"].split("playerid=")[1].split("&")[0]
        )

        if obj.count() > 0:
            obj = obj[0]

            stats_dict["g"] = to_int(h[6].text)
            stats_dict["gs"] = to_int(h[7].text)
            stats_dict["k"] = to_int(h[9].text)
            stats_dict["bb"] = to_int(h[10].text)
            stats_dict["ha"] = to_int(h[11].text)
            stats_dict["hra"] = to_int(h[12].text)
            stats_dict["ip"] = to_float(h[8].text.replace("%", ""))
            stats_dict["k_9"] = to_float(h[13].text.replace("%", ""))
            stats_dict["bb_9"] = to_float(h[14].text.replace("%", ""))
            stats_dict["hr_9"] = to_float(h[15].text.replace("%", ""))
            stats_dict["lob_pct"] = to_float(h[17].text.replace("%", ""))
            stats_dict["gb_pct"] = to_float(h[18].text.replace("%", ""))
            stats_dict["hr_fb"] = to_float(h[19].text.replace("%", ""))
            stats_dict["era"] = to_float(h[21].text.replace("%", ""))
            stats_dict["fip"] = to_float(h[23].text.replace("%", ""))
            stats_dict["xfip"] = to_float(h[24].text.replace("%", ""))
            stats_dict["siera"] = to_float(h[25].text.replace("%", ""))
            stats_dict["er"] = to_float(h[27].text.replace("%", ""))
            stats_dict["k_9+"] = to_int(h[28].text)
            stats_dict["bb_9+"] = to_int(h[29].text)
            stats_dict["era-"] = to_int(h[30].text)
            stats_dict["fip-"] = to_int(h[31].text)
            stats_dict["xfip-"] = to_int(h[32].text)

            obj.set_stats(stats_dict)
            obj.save()

            current_dict = stats_dict.copy()
            current_dict["slug"] = "current"

            obj.set_stats(current_dict)
            obj.save()


# def aggregate_team_stats_season(self):
#     def set_hitters(team):
#         for field in [
#             "ls_hits",
#             "ls_2b",
#             "ls_3b",
#             "ls_hr",
#             "ls_sb",
#             "ls_runs",
#             "ls_rbi",
#             "ls_plate_appearances",
#             "ls_ab",
#             "ls_bb",
#             "ls_k",
#         ]:
#             setattr(
#                 team,
#                 field,
#                 models.Player.objects.filter(role="MLB", team=team)
#                 .exclude(position="P")
#                 .aggregate(Sum(field))[f"{field}__sum"],
#             )

#         team.ls_avg = to_float(team.ls_hits) / to_float(team.ls_ab)
#         team.ls_obp = (team.ls_hits + team.ls_bb) / to_float(team.ls_plate_appearances)
#         teamtb = (
#             (team.ls_hits - team.ls_hr - team.ls_2b - team.ls_3b)
#             + (team.ls_2b * 2)
#             + (team.ls_3b * 3)
#             + (team.ls_hr * 4)
#         )
#         team.ls_slg = teamtb / to_float(team.ls_plate_appearances)
#         team.ls_iso = team.ls_slg - team.ls_avg
#         team.ls_k_pct = team.ls_k / to_float(team.ls_plate_appearances)
#         team.ls_bb_pct = team.ls_bb / to_float(team.ls_plate_appearances)

#     def set_pitchers(team):
#         for field in [
#             "ls_g",
#             "ls_gs",
#             "ls_ip",
#             "ls_pk",
#             "ls_pbb",
#             "ls_ha",
#             "ls_hra",
#             "ls_er",
#         ]:
#             setattr(
#                 team,
#                 field,
#                 models.Player.objects.filter(role="MLB", team=team).aggregate(
#                     Sum(field)
#                 )[f"{field}__sum"],
#             )

#         team.ls_era = (team.ls_er / to_float(team.ls_ip)) * 9.0
#         team.ls_k_9 = (team.ls_pk / to_float(team.ls_ip)) * 9.0
#         team.ls_bb_9 = (team.ls_pbb / to_float(team.ls_ip)) * 9.0
#         team.ls_hr_9 = (team.ls_hra / to_float(team.ls_ip)) * 9.0
#         team.ls_hits_9 = (team.ls_ha / to_float(team.ls_ip)) * 9.0
#         team.ls_whip = (team.ls_ha + team.ls_bb) / to_float(team.ls_ip)

#     for team in models.Team.objects.all():
#         set_hitters(team)
#         set_pitchers(team)
#         team.save()


def set_carded(*args, **options):
    season = get_current_season()

    if not options.get("dry_run", None):
        models.Player.objects.all().update(is_carded=False)
        models.Player.objects.filter(
            stats__current__year=season, stats__current__type="majors"
        ).update(is_carded=True)
    else:
        print(models.Player.objects.filter(stats__current__year=season).count())


def reset_rosters(*args, **options):
    if not options.get("dry_run", None):
        models.Player.objects.filter(is_mlb_roster=True).update(is_mlb_roster=False)
        models.Player.objects.filter(is_aaa_roster=True).update(is_aaa_roster=False)
        models.Player.objects.filter(is_35man_roster=True).update(is_35man_roster=False)
        models.Player.objects.filter(is_1h_c=True).update(is_1h_c=False)
        models.Player.objects.filter(is_1h_p=True).update(is_1h_p=False)
        models.Player.objects.filter(is_1h_pos=True).update(is_1h_pos=False)
        models.Player.objects.filter(is_reserve=True).update(is_reserve=False)

        models.Player.objects.filter(is_2h_c=True).update(is_2h_c=False)
        models.Player.objects.filter(is_2h_p=True).update(is_2h_p=False)
        models.Player.objects.filter(is_2h_pos=True).update(is_2h_pos=False)
        models.Player.objects.filter(is_2h_draft=True).update(is_2h_draft=False)

        # Unprotect all V and A players prior to the 35-man roster.
        models.Player.objects.filter(is_owned=True, level__in=["A", "V"]).update(
            is_protected=False
        )
        models.Player.objects.filter(
            is_owned=True, is_carded=False, level__in=["A", "V"]
        ).update(is_protected=True)


def load_career_hit(*args, **options):
    """
    https://www.fangraphs.com/leaders.aspx?pos=all&stats=bat&lg=all&qual=250&type=8&season=2022&month=0&season1=2000&ind=0&team=0&rost=0&age=&filter=&players=0&startdate=&enddate=&page=1_5000
    """

    hostname = get_hostname()
    scriptname = get_scriptname()
    timestamp = generate_timestamp()

    print(f"{timestamp}\tcareer\tload_career_hit")

    with open("data/career/hit.csv", "r") as readfile:
        players = csv.DictReader(readfile)
        for row in [dict(z) for z in players]:
            try:
                p = models.Player.objects.get(fg_id=row["playerid"])
                if not p.stats.get("career", None):
                    p.stats["career"] = {}
                    p.stats["career"]["pa"] = None

                p.stats["career"]["year"] = "career"
                p.stats["career"]["type"] = "majors"
                p.stats["career"]["timestamp"] = timestamp
                p.stats["career"]["level"] = "mlb"
                p.stats["career"]["side"] = "pitch"
                p.stats["career"]["script"] = scriptname
                p.stats["career"]["host"] = hostname
                p.stats["career"][
                    "slug"
                ] = f"{ p.stats['career']['year']}_{ p.stats['career']['type']}"

                p.stats["career"]["pa"] = int(row["PA"])

                if not options.get("dry_run", None):
                    p.save()

            except:
                pass


def load_career_pitch(*args, **options):
    """
    https://www.fangraphs.com/leaders.aspx?pos=all&stats=pit&lg=all&qual=30&type=8&season=2022&month=0&season1=2000&ind=0&team=0&rost=0&age=0&filter=&players=0&startdate=&enddate=&page=1_5000
    """

    hostname = get_hostname()
    scriptname = get_scriptname()
    timestamp = generate_timestamp()

    print(f"{timestamp}\tcareer\tload_career_pitch")

    with open("data/career/pitch.csv", "r") as readfile:
        players = csv.DictReader(readfile)
        for row in [dict(z) for z in players]:
            try:
                p = models.Player.objects.get(fg_id=row["playerid"])
                if not p.stats.get("career", None):
                    p.stats["career"] = {}

                    p.stats["career"]["gs"] = None
                    p.stats["career"]["g"] = None
                    p.stats["career"]["ip"] = None

                p.stats["career"]["year"] = "career"
                p.stats["career"]["type"] = "majors"
                p.stats["career"]["timestamp"] = timestamp
                p.stats["career"]["level"] = "mlb"
                p.stats["career"]["side"] = "pitch"
                p.stats["career"]["script"] = scriptname
                p.stats["career"]["host"] = hostname
                p.stats["career"][
                    "slug"
                ] = f"{ p.stats['career']['year']}_{ p.stats['career']['type']}"

                p.stats["career"]["gs"] = int(row["GS"])
                p.stats["career"]["g"] = int(row["G"])
                p.stats["career"]["ip"] = int(row["IP"].split(".")[0])

                if not options.get("dry_run", None):
                    p.save()

            except:
                pass


def set_levels(*args, **options):
    print("--------- STARTERS B > A ---------")
    for p in models.Player.objects.filter(
        level="B", position="P", stats__career__gs__gte=21
    ):
        p.level = "A"
        print(p)
        if not options.get("dry_run", None):
            p.save()

    print("--------- RELIEVERS B > A ---------")
    for p in models.Player.objects.filter(
        level="B", position="P", stats__career__g__gte=31
    ):
        p.level = "A"
        print(p)
        if not options.get("dry_run", None):
            p.save()
    print("--------- SWINGMEN B > A ---------")
    for p in models.Player.objects.filter(
        level="B", position="P", stats__career__g__gte=40, stats__career__gs__gte=15
    ):
        p.level = "A"
        print(p)
        if not options.get("dry_run", None):
            p.save()

    print("--------- HITTERS B > A ---------")
    for p in models.Player.objects.filter(level="B", stats__career__pa__gte=300):
        p.level = "A"
        print(p)
        if not options.get("dry_run", None):
            p.save()

    print("--------- STARTERS A > V ---------")
    for p in models.Player.objects.filter(
        level="A", position="P", stats__career__gs__gte=126
    ):
        p.level = "V"
        print(p)
        if not options.get("dry_run", None):
            p.save()

    print("--------- RELIEVERS A > V ---------")
    for p in models.Player.objects.filter(
        level="A", position="P", stats__career__g__gte=201
    ):
        p.level = "V"
        print(p)
        if not options.get("dry_run", None):
            p.save()

    print("--------- SWINGMEN A > V ---------")
    for p in models.Player.objects.filter(
        level="A", position="P", stats__career__g__gte=220, stats__career__gs__gte=30
    ):
        p.level = "V"
        print(p)
        if not options.get("dry_run", None):
            p.save()

    print("--------- HITTERS A > V ---------")
    for p in models.Player.objects.filter(level="A", stats__career__pa__gte=2500):
        p.level = "V"
        print(p)
        if not options.get("dry_run", None):
            p.save()
