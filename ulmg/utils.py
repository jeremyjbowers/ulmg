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
    if player.fg_id:
        player_url = f"https://www.fangraphs.com/statss.aspx?playerid={player.fg_id}"
        r = requests.get(player_url)
        soup = BeautifulSoup(r.content)
        
        try:
            date_cell = soup.select('tr.player-info__bio-birthdate td')[0].text
            player.birthdate = parse(date_cell.split('(')[0].strip())
            player.birthdate_qa = True
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
        models.Player.objects.filter(**{lookup: keyword}).update(stats={})

    else:
        models.Player.objects.filter(stats__isnull=False).update(stats={})


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
    name_fragment, score=0.7, position=None, mlb_org=None
):

    output = []

    players = models.Player.objects

    if position:
        players = players.filter(position=position)

    if mlb_org:
        players = players.filter(mlb_org=mlb_org)

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
    first_initial, last_name, hitter=True, mlb_org=None, ulmg_id=None
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
        if mlb_org:
            players = players.filter(mlb_org=mlb_org)

    if len(players) == 0:
        return None

    return players[0]


def fuzzy_find_player(name_fragment, score=0.7, position=None, mlb_org=None):

    players = models.Player.objects

    if position:
        players = players.filter(position=position)

    if mlb_org:
        players = players.filter(mlb_org=mlb_org)

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
    return "DH"


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