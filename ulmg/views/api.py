import csv
import datetime

from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import render, get_object_or_404
from django.db.models import Count, Avg, Sum, Max, Min, Q
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.conf import settings
import ujson as json

from ulmg import models, utils


@login_required
@csrf_exempt
def get_wishlist_players(request):
    owner = models.Owner.objects.get(user=request.user)
    w = models.Wishlist.objects.filter(owner=owner)
    wishlist = None
    wishlist_players = []
    if len(w) > 0:
        wishlist = w[0]
    if wishlist:
        for p in models.WishlistPlayer.objects.filter(wishlist=wishlist).order_by(
            "-player__team", "player__last_name"
        ):
            player_dict = {
                "player": p.player.name,
                "id": p.player.id,
                "level": p.player.level,
                "position": p.player.position,
                "age": p.player.age,
                "url": f"/players/{ p.player.id }/",
                "mlb_team": p.player.mlb_org,
                "team": None,
                "stats": None,
            }

            if p.player.team:
                player_dict["team"] = p.player.team.abbreviation

            wishlist_players.append(player_dict)

    return JsonResponse({"players": wishlist_players})


@login_required
@csrf_exempt
def trade_bulk_action(request):
    for raw_json_string, _ in request.POST.items():
        trade_payload = json.loads(raw_json_string)

        trade = models.Trade.objects.create(date=datetime.datetime.today())

        team_1 = models.Team.objects.get(
            abbreviation__icontains=trade_payload[0]["team"]
        )
        players_1 = [
            models.Player.objects.get(id=f.split("player-")[1])
            for f in trade_payload[1]["receipt"]
            if "player-" in f
        ]
        picks_1 = [
            models.DraftPick.objects.get(id=f.split("pick-")[1])
            for f in trade_payload[1]["receipt"]
            if "pick-" in f
        ]

        team_2 = models.Team.objects.get(
            abbreviation__icontains=trade_payload[1]["team"]
        )
        players_2 = [
            models.Player.objects.get(id=f.split("player-")[1])
            for f in trade_payload[0]["receipt"]
            if "player-" in f
        ]
        picks_2 = [
            models.DraftPick.objects.get(id=f.split("pick-")[1])
            for f in trade_payload[0]["receipt"]
            if "pick-" in f
        ]

        tr_1 = models.TradeReceipt.objects.create(trade=trade, team=team_1)
        for p in players_1:
            tr_1.players.add(p)

        for p in picks_1:
            tr_1.picks.add(p)

        tr_1.save()

        tr_2 = models.TradeReceipt.objects.create(trade=trade, team=team_2)
        for p in players_2:
            tr_2.players.add(p)

        for p in picks_2:
            tr_2.picks.add(p)

        tr_2.save()

        trade.set_trade_summary()
        trade.set_teams()
        trade.save()

    return JsonResponse({"success": True})

    # except Exception as e:
    #     return JsonResponse({"success": False, "error": f"{e}"})


@login_required
@csrf_exempt
def wishlist_bulk_action(request):
    for raw_json_string, _ in request.POST.items():
        players = json.loads(raw_json_string)
        for p in players:
            models.WishlistPlayer.objects.filter(player__id=p["playerid"]).update(
                rank=p["rank"]
            )

    return JsonResponse({"success": True, "updated": len(players)})


@login_required
@csrf_exempt
def wishlist_player_action(request, playerid):
    context = utils.build_context(request)
    wishlist = None
    wl = models.Wishlist.objects.filter(owner=context["owner"])
    if len(wl) > 0:
        wishlist = wl[0]

    w = utils.update_wishlist(
        playerid,
        wishlist,
        request.GET.get("rank", None),
        request.GET.get("tier", None),
        remove=utils.str_to_bool(request.GET.get("remove")),
    )

    if w:
        return JsonResponse({"success": True, "player": w})

    return JsonResponse({"success": False, "player": w})


@login_required
@csrf_exempt
def player_action(request, playerid, action):
    p = get_object_or_404(models.Player, id=playerid)

    if action == "trade_block":
        if p.is_trade_block:
            p.is_trade_block = False
        else:
            p.is_trade_block = True
        p.save()

        return HttpResponse("ok")

    if action == "to_35_man":
        p.is_reserve = False
        p.is_1h_c = False
        p.is_1h_p = False
        p.is_1h_pos = False
        p.is_35man_roster = True
        p.is_protected = True
        p.save()
        return HttpResponse("ok")

    if action == "unprotect":
        p.is_reserve = False
        p.is_1h_c = False
        p.is_1h_p = False
        p.is_1h_pos = False
        # p.is_2h_c = False
        # p.is_2h_p = False
        # p.is_2h_pos = False
        p.is_35man_roster = False
        p.is_mlb_roster = False
        p.is_aaa_roster = False
        p.is_protected = False
        p.save()
        return HttpResponse("ok")

    if action == "is_reserve":
        old = models.Player.objects.filter(team=p.team, is_reserve=True).update(
            is_reserve=False
        )
        p.is_reserve = False
        p.is_1h_c = False
        p.is_1h_p = False
        p.is_1h_pos = False
        p.is_35man_roster = False
        p.is_reserve = True
        p.is_mlb_roster = False
        p.is_aaa_roster = False
        p.save()
        return HttpResponse("ok")

    # if action == "is_2h_p":
    #     old = models.Player.objects.filter(team=p.team, is_2h_p=True).update(
    #         is_2h_p=False
    #     )
    #     p.is_reserve = False
    #     p.is_2h_c = False
    #     p.is_2h_p = False
    #     p.is_2h_pos = False
    #     p.is_2h_p = True
    #     p.is_mlb_roster = False
    #     p.is_aaa_roster = False
    #     p.save()
    #     return HttpResponse("ok")

    # if action == "is_2h_c":
    #     old = models.Player.objects.filter(team=p.team, is_2h_c=True).update(
    #         is_2h_c=False
    #     )
    #     p.is_reserve = False
    #     p.is_2h_c = False
    #     p.is_2h_p = False
    #     p.is_2h_pos = False
    #     p.is_2h_c = True
    #     p.is_mlb_roster = False
    #     p.is_aaa_roster = False
    #     p.save()
    #     return HttpResponse("ok")

    # if action == "is_2h_pos":
    #     old = models.Player.objects.filter(team=p.team, is_2h_pos=True).update(
    #         is_2h_pos=False
    #     )
    #     p.is_reserve = False
    #     p.is_2h_c = False
    #     p.is_2h_p = False
    #     p.is_2h_pos = False
    #     p.is_2h_pos = True
    #     p.is_mlb_roster = False
    #     p.is_aaa_roster = False
    #     p.save()
    #     return HttpResponse("ok")

    if action == "is_1h_p":
        old = models.Player.objects.filter(team=p.team, is_1h_p=True).update(
            is_1h_p=False
        )
        p.is_reserve = False
        p.is_1h_c = False
        p.is_1h_p = False
        p.is_1h_pos = False
        p.is_35man_roster = False
        p.is_1h_p = True
        p.is_mlb_roster = False
        p.is_aaa_roster = False
        p.save()
        return HttpResponse("ok")

    if action == "is_1h_c":
        old = models.Player.objects.filter(team=p.team, is_1h_c=True).update(
            is_1h_c=False
        )
        p.is_reserve = False
        p.is_1h_c = False
        p.is_1h_p = False
        p.is_1h_pos = False
        p.is_35man_roster = False
        p.is_1h_c = True
        p.is_mlb_roster = False
        p.is_aaa_roster = False
        p.save()
        return HttpResponse("ok")

    if action == "is_1h_pos":
        old = models.Player.objects.filter(team=p.team, is_1h_pos=True).update(
            is_1h_pos=False
        )
        p.is_reserve = False
        p.is_1h_c = False
        p.is_1h_p = False
        p.is_1h_pos = False
        p.is_35man_roster = False
        p.is_1h_pos = True
        p.is_mlb_roster = False
        p.is_aaa_roster = False
        p.save()
        return HttpResponse("ok")

    if action == "to_mlb":
        p.is_mlb_roster = True
        p.is_aaa_roster = False
        p.is_reserve = False
        p.is_1h_c = False
        p.is_1h_p = False
        p.is_1h_pos = False
        p.is_2h_c = False
        p.is_2h_p = False
        p.is_2h_pos = False
        p.is_2h_pos = False
        p.save()
        return HttpResponse("ok")

    if action == "to_aaa":
        p.is_mlb_roster = False
        p.is_aaa_roster = True
        p.is_reserve = False
        p.is_1h_c = False
        p.is_1h_p = False
        p.is_1h_pos = False
        p.is_2h_c = False
        p.is_2h_p = False
        p.is_2h_pos = False
        p.is_2h_pos = False
        p.save()
        return HttpResponse("ok")

    if action == "off_roster":
        p.is_mlb_roster = False
        p.is_aaa_roster = False
        p.is_reserve = False
        p.is_1h_c = False
        p.is_1h_p = False
        p.is_1h_pos = False
        p.is_2h_c = False
        p.is_2h_p = False
        p.is_2h_pos = False
        p.is_2h_pos = False
        p.save()
        return HttpResponse("ok")

    if action == "drop":
        p.is_mlb_roster = False
        p.is_aaa_roster = False
        p.team = None
        p.is_owned = False
        p.is_reserve = False
        p.is_1h_c = False
        p.is_1h_p = False
        p.is_1h_pos = False
        p.is_2h_c = False
        p.is_2h_p = False
        p.is_2h_pos = False
        p.is_protected = False
        p.save()
        return HttpResponse("ok")

    return HttpResponse("error")


@login_required
def draft_api(request, year, season, draft_type):
    context = {}
    context["picks"] = [
        p.to_dict()
        for p in models.DraftPick.objects.filter(
            year=year, season=season, draft_type=draft_type
        )
    ]
    context["year"] = year
    context["season"] = season
    context["draft_type"] = draft_type

    return JsonResponse(context)


@login_required
@csrf_exempt
def draft_action(request, pickid):
    playerid = None
    name = None
    skipped = None

    if request.GET.get("name", None):
        name = request.GET["name"]

    if request.GET.get("playerid", None):
        playerid = request.GET("playerid")

    if request.GET.get("skipped", None):
        skipped = True

    draftpick = get_object_or_404(models.DraftPick, pk=pickid)

    if skipped:
        draftpick.player = None
        draftpick.skipped = True
        draftpick.save()

    if playerid:
        draftpick.player = get_object_or_404(models.Player, pk=playerid)
        draftpick.player.team = draftpick.team
        draftpick.player.is_mlb_roster = True
        draftpick.player.save()
        draftpick.save()

    if name:
        if "(" in name:
            name = name.split("(")[0].strip()
        ps = models.Player.objects.filter(name=name)
        if len(ps) == 1:
            draftpick.player = ps[0]
            draftpick.player.team = draftpick.team
            draftpick.player.is_mlb_roster = True
            draftpick.player.save()
        else:
            draftpick.player_name = name
        draftpick.save()

    if not name and not playerid:
        if draftpick.player:
            draftpick.player.team = None
            draftpick.player.is_mlb_roster = False
            draftpick.player.save()
            draftpick.player = None

        if draftpick.player_name:
            draftpick.player_name = None

        draftpick.save()

    return HttpResponse("ok")


@login_required
def player_list(request):
    is_carded = request.GET.get("is_carded", None)
    is_owned = request.GET.get("is_owned", None)
    ids = request.GET.get("ids", None)

    query = models.Player.objects

    if ids:
        query = query.filter(Q(fg_id__in=ids.split(",")) | Q(fg_id__isnull=True))

    if is_carded:
        query = query.filter(is_carded=utils.str_to_bool(is_carded))

    if is_owned:
        query = query.filter(is_owned=utils.str_to_bool(is_owned))

    payload = [
        {
            "name": p.name,
            "fg_id": p.fg_id,
            "is_carded": p.is_carded,
            "is_owned": p.is_owned,
            "level": p.level,
            "age": p.age,
            "position": p.position,
            "def": p.defense_display(),
            "team": p.team_display(),
            "amateur": p.is_amateur,
        }
        for p in query
    ]

    return JsonResponse(payload, safe=False)


@login_required
def scouting_report(request, playerid):
    p = get_object_or_404(models.Player, id=playerid)
    payload = {}
    payload["name"] = p.name
    payload["position"] = p.position
    payload["notes"] = p.notes
    payload["mlb_team"] = "No MLB team"
    if p.mlb_team:
        payload["mlb_team"] = p.mlb_team
    return JsonResponse(payload, safe=False)


@login_required
def search(request):
    def to_bool(b):
        if b.lower() in ["y", "yes", "t", "true", "on"]:
            return True
        return False

    context = utils.build_context(request)

    query = models.Player.objects.all()

    if request.GET.get("protected", None):
        protected = request.GET["protected"]
        if protected.lower() != "":
            if to_bool(protected) == False:
                query = query.filter(
                    Q(is_1h_c=False),
                    Q(is_1h_p=False),
                    Q(is_1h_pos=False),
                    Q(is_35man_roster=False),
                    Q(is_reserve=False),
                )
            else:
                query = query.filter(
                    Q(is_1h_c=True)
                    | Q(is_1h_p=True)
                    | Q(is_1h_pos=True)
                    | Q(is_35man_roster=True)
                    | Q(is_reserve=True)
                )

            context["protected"] = protected

    if request.GET.get("name", None):
        name = request.GET["name"]
        query = query.filter(name__search=name)
        context["name"] = name

    if request.GET.get("position", None):
        position = request.GET["position"]
        if position.lower() not in ["", "h"]:
            query = query.filter(position__icontains=position)
            context["position"] = position
        elif position.lower() == "h":
            query = query.exclude(position="P")
            context["position"] = position

    if request.GET.get("level", None):
        level = request.GET["level"]
        if level.lower() != "":
            query = query.filter(level=level)
            context["level"] = level

    if request.GET.get("reliever", None):
        reliever = request.GET["reliever"]
        if reliever.lower() != "":
            query = query.filter(is_relief_eligible=to_bool(reliever))
            if to_bool(reliever) == False:
                query = query.filter(starts__isnull=False).exclude(starts=0)
            context["reliever"] = reliever

    if request.GET.get("prospect", None):
        prospect = request.GET["prospect"]
        if prospect.lower() != "":
            query = query.filter(is_prospect=to_bool(prospect))
            context["prospect"] = prospect

    if request.GET.get("owned", None):
        owned = request.GET["owned"]
        if owned.lower() != "":
            query = query.filter(is_owned=to_bool(owned))
            context["owned"] = owned

    if request.GET.get("carded", None):
        carded = request.GET["carded"]
        if carded.lower() != "":
            query = query.filter(is_carded=to_bool(carded))
            context["carded"] = carded

    if request.GET.get("amateur", None):
        amateur = request.GET["amateur"]
        if amateur.lower() != "":
            query = query.filter(is_amateur=to_bool(amateur))
            context["amateur"] = amateur

    query = query.order_by("level", "last_name")

    if request.GET.get("csv", None):
        c = request.GET["csv"]
        if c.lower() in ["y", "yes", "t", "true"]:
            query = query.values(*settings.CSV_COLUMNS)
            response = HttpResponse(content_type="text/csv")
            response["Content-Disposition"] = 'attachment; filename="search-%s.csv"' % (
                datetime.datetime.now().isoformat().split(".")[0]
            )
            writer = csv.DictWriter(response, fieldnames=settings.CSV_COLUMNS)
            writer.writeheader()
            for p in query:
                writer.writerow(p)
            return response

    query = query.order_by("position", "-level_order", "last_name")

    context["hitters"] = query.exclude(position="P")
    context["pitchers"] = query.filter(position="P")
    return render(request, "search.html", context)


@csrf_exempt
def player_detail(request):
    if request.method == "GET":
        if request.GET.get("id_type", None):
            if request.GET.get("playerid", None):
                id_type = request.GET["id_type"]
                playerid = request.GET["playerid"]

                search_dict = {id_type: playerid}
                p = models.Player.objects.get(**search_dict)
                return JsonResponse(p.to_api_obj())
    return None


@csrf_exempt
def player_owned(request):
    if request.method == "POST":
        if request.POST.get("text", None):
            players = models.Player.objects.filter(name__search=request.POST["text"])
            if len(players) > 0:
                payload = []
                for p in players:
                    if p.is_owned:
                        payload.append(
                            f"{p.position} <http://theulmg.com/players/{p.id}/|{p.name}> is owned by <http://theulmg.com/teams/{p.team.abbreviation}/|{p.team}>"
                        )
                    else:
                        payload.append(
                            f"{p.position} <http://theulmg.com/players/{p.id}/|{p.name}> is unowned."
                        )
                return HttpResponse("\n".join(payload))
            else:
                return HttpResponse(
                    f'I don\'t see a player named {request.POST["text"]} in the ULMG database.'
                )
        else:
            return HttpResponse("Ooops, please give me a player name to search for.")
    else:
        return HttpResponse("Not a POST.")


"""
Konnor Griffin  OF
Samuel Cozart   P
Dean Moss   OF
Carter Smith    IF
Jacob Kendall   IF
Luis Ayden Almeyda  IF
John Lash   P
Xavier Neyens   IF
Cam Caminiti    OF
Sean Gamble IF
Derek Curiel    OF
Chase Mobley    Paul
Cade Arrambide  C
Bryce Rainer    IF
Theodore Gillen IF
Michael Mullinax    OF
Jackson Sanders P
Jack Frankel    P
George Wolkow   IF
Andre Modugno   IF
Deion Cole  IF
Rouselle Shepard    IF
Quentin Young   IF
Grady Emerson   IF
Kevin Roberts Jr    IF
Grant Mehrhoff  P
Alex Harrington IF
Beau Peterson   C
Ryan Harwood    IF
Andrew Costello C
"""


@csrf_exempt
def player_bulk_action(request):
    payload = {"players": []}

    if request.method == "POST":
        if request.POST.get("players", None):

            player_list = request.POST.get("players").split("\n")

            for p in player_list:

                if "\t" in p:
                    player = p.split("\t")

                elif "," in p:
                    player = p.split(",")

                if len(player) > 1:

                    name = player[0]
                    position = player[1]
                    ply = {
                        "name": name,
                        "position": position,
                        "ulmg_id": None,
                        "created": False,
                    }

                    plyrz = utils.fuzzy_find_player(name)

                    if len(plyrz) == 1:
                        ply["ulmg_id"] = plyrz[0].id

                    elif len(plyrz) == 0:
                        p = models.Player(
                            name=name,
                            level="B",
                            is_prospect=True,
                            is_amateur=True,
                            position=position
                        )
                        p.save()
                        ply["ulmg_id"] = p.id
                        ply["created"] = True

                    payload["players"].append(ply)

    return JsonResponse(payload)


@csrf_exempt
def delete_tag_from_wishlistplayer(request, playerid):
    context = utils.build_context(request)
    if request.method == "POST":
        if request.POST.get("tagname", None):

            tagname = request.POST.get("tagname")

            w = models.WishlistPlayer.objects.get(
                player__id=playerid, wishlist__owner=context["owner"]
            )

            tags = []

            for t in w.tags:
                if t != tagname:
                    tags.append(t)

            w.tags = tags
            w.save()

    return JsonResponse({"message": "ok"})


@csrf_exempt
def add_tag_to_wishlistplayer(request, playerid):
    context = utils.build_context(request)
    if request.method == "POST":
        if request.POST.get("tagname", None):

            tagname = request.POST.get("tagname")

            w = models.WishlistPlayer.objects.get(
                player__id=playerid, wishlist__owner=context["owner"]
            )

            if not w.tags:
                w.tags = []

            w.tags.append(tagname)

            w.save()

    return JsonResponse({"message": "ok"})


@csrf_exempt
def add_note_to_wishlistplayer(request, playerid):
    context = {}
    context["owner"] = None
    if request.user.is_authenticated:
        owner = models.Owner.objects.get(user=request.user)
        context["owner"] = owner

    if request.method == "POST":
        if request.POST.get("note", None):

            note = request.POST.get("note")

            w = models.WishlistPlayer.objects.get(
                player__id=playerid, wishlist__owner=context["owner"]
            )
            w.note = note
            w.save()

    return JsonResponse({"message": "ok"})
