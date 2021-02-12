import pickle
import os.path

from googleapiclient.discovery import build
from google.oauth2 import service_account

from django.conf import settings
from django.contrib.postgres.search import TrigramSimilarity

from ulmg import models


def fuzzy_find_player(name_fragment, score=0.7):
    return (
        models.Player.objects.annotate(
            similarity=TrigramSimilarity("name", name_fragment)
        )
        .filter(similarity__gt=score)
        .order_by("-similarity")
    )


def update_wishlist(playerid, wishlist, tier, rank, remove=False):
    p = models.Player.objects.get(id=playerid)
    w, created = models.WishlistPlayer.objects.get_or_create(
        player=p, wishlist=wishlist
    )
    if remove:
        player_name = str(w.player.name)
        w.delete()
        return player_name
    else:
        w.tier = tier
        w.rank = rank
        w.save()
        return w.player.name


def build_context(request):
    context = {}

    # to build the nav
    context["teamnav"] = models.Team.objects.all().values("abbreviation")
    context["draftnav"] = settings.DRAFTS
    context["mlb_roster_size"] = settings.MLB_ROSTER_SIZE

    # for showing stats
    context["advanced"] = False
    if request.GET.get("adv", None):
        context["advanced"] = True

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

    # wishlist
    context["wishlist"] = None
    context["owner"] = None
    context["wishlist_players"] = []
    if request.user.is_authenticated:
        owner = models.Owner.objects.get(user=request.user)
        context["owner"] = owner
        w = models.Wishlist.objects.filter(owner=owner)
        if len(w) > 0:
            context["wishlist"] = w[0]
        context["wishlist_players"] = [
            p.player.id
            for p in models.WishlistPlayer.objects.filter(wishlist=context["wishlist"])
        ]

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
