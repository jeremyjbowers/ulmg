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
                "mlb_team": p.player.current_mlb_org,
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
    context = utils.build_context(request)
    wishlist = None
    wl = models.Wishlist.objects.filter(owner=context["owner"])
    if len(wl) > 0:
        wishlist = wl[0]

    for raw_json_string, _ in request.POST.items():
        players = json.loads(raw_json_string)
        for p in players:
            models.WishlistPlayer.objects.filter(wishlist=wishlist, player__id=p["playerid"]).update(
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
    p = models.Player.objects.get(id=playerid)
    current_season = datetime.datetime.now().year
    
    def _update_player_stat_season(player, **kwargs):
        """Update or create PlayerStatSeason with roster status fields."""
        # Get or create the most recent PlayerStatSeason for this player
        player_stat_season = models.PlayerStatSeason.objects.filter(
            player=player,
            season=current_season
        ).first()
        
        if not player_stat_season:
            # Create a new PlayerStatSeason for the current season
            player_stat_season = models.PlayerStatSeason.objects.create(
                player=player,
                season=current_season,
                classification='1-mlb',  # Default, will be corrected by stats updates
                owned=player.is_owned,
                carded=False  # Will be set by separate command
            )
        
        # Update the roster status fields
        for field, value in kwargs.items():
            if hasattr(player_stat_season, field):
                setattr(player_stat_season, field, value)
        
        player_stat_season.save()
        return player_stat_season

    if action == "to_35_man":
        p.is_reserve = False
        p.is_1h_c = False
        p.is_1h_p = False
        p.is_1h_pos = False
        p.is_protected = True
        p.save()
        _update_player_stat_season(p, is_ulmg35man_roster=True)
        return HttpResponse("ok")

    if action == "unprotect":
        p.is_reserve = False
        p.is_1h_c = False
        p.is_1h_p = False
        p.is_1h_pos = False
        p.is_ulmg_2h_c = False
        p.is_ulmg_2h_p = False
        p.is_ulmg_2h_pos = False
        p.is_protected = False
        # Update Player model roster status
        p.is_ulmg_mlb_roster = False
        p.is_ulmg_aaa_roster = False
        p.save()
        _update_player_stat_season(p, 
            is_ulmg35man_roster=False,
            is_ulmg_mlb_roster=False,
            is_ulmg_aaa_roster=False
        )
        return HttpResponse("ok")

    if action == "is_ulmg_reserve":
        old = models.Player.objects.filter(team=p.team, is_ulmg_reserve=True).update(
            is_ulmg_reserve=False
        )
        p.is_ulmg_reserve = True
        p.is_ulmg_1h_c = False
        p.is_ulmg_1h_p = False
        p.is_ulmg_1h_pos = False
        p.save()
        _update_player_stat_season(p, 
            is_ulmg35man_roster=False,
            is_ulmg_mlb_roster=False,
            is_ulmg_aaa_roster=False
        )
        return HttpResponse("ok")

    if action == "is_ulmg_2h_p":
        # Prevent 2H protections for 2H draft players (they must stay on rosters full 2H)
        if p.is_ulmg_2h_draft:
            return HttpResponse("error: 2H draft players cannot be protected")
        
        old = models.Player.objects.filter(team=p.team, is_ulmg_2h_p=True).update(
            is_ulmg_2h_p=False
        )
        p.is_ulmg_reserve = False
        p.is_ulmg_2h_c = False
        p.is_ulmg_2h_p = True
        p.is_ulmg_2h_pos = False
        p.save()
        _update_player_stat_season(p, 
            is_ulmg35man_roster=False,
            is_ulmg_mlb_roster=False,
            is_ulmg_aaa_roster=False
        )
        return HttpResponse("ok")

    if action == "is_ulmg_2h_c":
        # Prevent 2H protections for 2H draft players (they must stay on rosters full 2H)
        if p.is_ulmg_2h_draft:
            return HttpResponse("error: 2H draft players cannot be protected")
        
        old = models.Player.objects.filter(team=p.team, is_ulmg_2h_c=True).update(
            is_ulmg_2h_c=False
        )
        p.is_ulmg_reserve = False
        p.is_ulmg_2h_c = True
        p.is_ulmg_2h_p = False
        p.is_ulmg_2h_pos = False
        p.save()
        _update_player_stat_season(p, 
            is_ulmg35man_roster=False,
            is_ulmg_mlb_roster=False,
            is_ulmg_aaa_roster=False
        )
        return HttpResponse("ok")

    if action == "is_ulmg_2h_pos":
        # Prevent 2H protections for 2H draft players (they must stay on rosters full 2H)
        if p.is_ulmg_2h_draft:
            return HttpResponse("error: 2H draft players cannot be protected")
        
        old = models.Player.objects.filter(team=p.team, is_ulmg_2h_pos=True).update(
            is_ulmg_2h_pos=False
        )
        p.is_ulmg_reserve = False
        p.is_ulmg_2h_c = False
        p.is_ulmg_2h_p = False
        p.is_ulmg_2h_pos = True
        p.save()
        _update_player_stat_season(p, 
            is_ulmg35man_roster=False,
            is_ulmg_mlb_roster=False,
            is_ulmg_aaa_roster=False
        )
        return HttpResponse("ok")

    if action == "is_ulmg_1h_p":
        old = models.Player.objects.filter(team=p.team, is_ulmg_1h_p=True).update(
            is_ulmg_1h_p=False
        )
        p.is_ulmg_reserve = False
        p.is_ulmg_1h_c = False
        p.is_ulmg_1h_p = True
        p.is_ulmg_1h_pos = False
        p.save()
        _update_player_stat_season(p, 
            is_ulmg35man_roster=False,
            is_ulmg_mlb_roster=False,
            is_ulmg_aaa_roster=False
        )
        return HttpResponse("ok")

    if action == "is_ulmg_1h_c":
        old = models.Player.objects.filter(team=p.team, is_ulmg_1h_c=True).update(
            is_ulmg_1h_c=False
        )
        p.is_ulmg_reserve = False
        p.is_ulmg_1h_c = True
        p.is_ulmg_1h_p = False
        p.is_ulmg_1h_pos = False
        p.save()
        _update_player_stat_season(p, 
            is_ulmg35man_roster=False,
            is_ulmg_mlb_roster=False,
            is_ulmg_aaa_roster=False
        )
        return HttpResponse("ok")

    if action == "is_ulmg_1h_pos":
        old = models.Player.objects.filter(team=p.team, is_ulmg_1h_pos=True).update(
            is_ulmg_1h_pos=False
        )
        p.is_ulmg_reserve = False
        p.is_ulmg_1h_c = False
        p.is_ulmg_1h_p = False
        p.is_ulmg_1h_pos = True
        p.save()
        _update_player_stat_season(p, 
            is_ulmg35man_roster=False,
            is_ulmg_mlb_roster=False,
            is_ulmg_aaa_roster=False
        )
        return HttpResponse("ok")



    if action == "to_mlb":
        p.is_reserve = False
        p.is_1h_c = False
        p.is_1h_p = False
        p.is_1h_pos = False
        p.is_2h_c = False
        p.is_2h_p = False
        p.is_2h_pos = False
        # Update Player model roster status
        p.is_ulmg_mlb_roster = True
        p.is_ulmg_aaa_roster = False
        p.save()
        _update_player_stat_season(p, 
            is_ulmg_mlb_roster=True,
            is_ulmg_aaa_roster=False
        )
        return HttpResponse("ok")

    if action == "to_aaa":
        p.is_reserve = False
        p.is_1h_c = False
        p.is_1h_p = False
        p.is_1h_pos = False
        p.is_2h_c = False
        p.is_2h_p = False
        p.is_2h_pos = False
        # Update Player model roster status
        p.is_ulmg_mlb_roster = False
        p.is_ulmg_aaa_roster = True
        p.save()
        _update_player_stat_season(p, 
            is_ulmg_mlb_roster=False,
            is_ulmg_aaa_roster=True
        )
        return HttpResponse("ok")

    if action == "off_roster":
        p.is_reserve = False
        p.is_1h_c = False
        p.is_1h_p = False
        p.is_1h_pos = False
        p.is_2h_c = False
        p.is_2h_p = False
        p.is_2h_pos = False
        # Update Player model roster status
        p.is_ulmg_mlb_roster = False
        p.is_ulmg_aaa_roster = False
        p.save()
        _update_player_stat_season(p, 
            is_ulmg_mlb_roster=False,
            is_ulmg_aaa_roster=False
        )
        return HttpResponse("ok")

    if action == "drop":
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
        # Update Player model roster status
        p.is_ulmg_mlb_roster = False
        p.is_ulmg_aaa_roster = False
        p.save()
        _update_player_stat_season(p, 
            is_ulmg_mlb_roster=False,
            is_ulmg_aaa_roster=False,
            owned=False
        )
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
def draft_watch_status(request, year, season, draft_type):
    """
    API endpoint for draft watch page to poll for updates
    Returns current draft status with timestamps for change detection
    """
    from django.db.models import Q
    
    # Get made picks (picks that have been made or skipped)
    made_picks = models.DraftPick.objects.filter(
        Q(player_name__isnull=False) | Q(player__isnull=False) | Q(skipped=True)
    ).filter(
        year=year, season=season, draft_type=draft_type
    ).order_by("year", "-season", "draft_type", "-draft_round", "-pick_number")
    
    # Get upcoming picks (picks that haven't been made yet)
    upcoming_picks = models.DraftPick.objects.filter(
        year=year, season=season, draft_type=draft_type
    ).exclude(Q(player_name__isnull=False) | Q(player__isnull=False) | Q(skipped=True))
    
    # Convert to dictionaries for JSON response
    made_picks_data = []
    for pick in made_picks:
        pick_data = {
            'id': pick.id,
            'pick_number': pick.pick_number,
            'draft_round': pick.draft_round,
            'team': pick.team.abbreviation if pick.team else '',
            'team_name': f"{pick.team.city} {pick.team.nickname}" if pick.team else '',
            'original_team': pick.original_team.abbreviation if pick.original_team else '',
            'player_name': pick.player_name or '',
            'player_position': pick.player.position if pick.player else '',
            'player_id': pick.player.id if pick.player else None,
            'skipped': pick.skipped,
            'updated_at': pick.updated_at.isoformat() if hasattr(pick, 'updated_at') and pick.updated_at else None
        }
        made_picks_data.append(pick_data)
    
    upcoming_picks_data = []
    for pick in upcoming_picks:
        pick_data = {
            'id': pick.id,
            'pick_number': pick.pick_number,
            'draft_round': pick.draft_round,
            'team': pick.team.abbreviation if pick.team else '',
            'team_name': f"{pick.team.city} {pick.team.nickname}" if pick.team else '',
            'original_team': pick.original_team.abbreviation if pick.original_team else '',
        }
        upcoming_picks_data.append(pick_data)
    
    response_data = {
        'made_picks': made_picks_data,
        'upcoming_picks': upcoming_picks_data,
        'year': year,
        'season': season,
        'draft_type': draft_type,
        'timestamp': datetime.datetime.now().isoformat()
    }
    
    return JsonResponse(response_data)


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
        # Handle old format with parentheses: "Name (extra info)"
        if "(" in name:
            name = name.split("(")[0].strip()
            ps = models.Player.objects.filter(name=name)
        elif "|" in name:
            # Handle new format with pk: "POS Name [TEAM] [MLBAM_ID] | PK"
            # Extract the pk from the end of the string
            try:
                pk = int(name.split("|")[-1].strip())
                ps = models.Player.objects.filter(pk=pk)
            except (ValueError, TypeError, IndexError):
                # If pk parsing fails, fall back to name parsing
                display_name = name.split("|")[0].strip()
                name_parts = display_name.split()
                if len(name_parts) >= 2:
                    # Extract just the name part (skip position)
                    player_name = " ".join(name_parts[1:])
                    ps = models.Player.objects.filter(name__icontains=player_name)
                else:
                    ps = []
        else:
            # Fallback for any other format - try name search
            ps = models.Player.objects.filter(name__icontains=name)
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
            current_season = datetime.datetime.now().year
            if to_bool(protected) == False:
                # Get players that are NOT protected
                query = query.filter(
                    Q(is_1h_c=False),
                    Q(is_1h_p=False),
                    Q(is_1h_pos=False),
                    Q(is_reserve=False),
                ).exclude(
                    Q(playerstatseason__season=current_season, playerstatseason__is_35man_roster=True)
                )
            else:
                # Get players that ARE protected
                query = query.filter(
                    Q(is_1h_c=True)
                    | Q(is_1h_p=True)
                    | Q(is_1h_pos=True)
                    | Q(is_reserve=True)
                    | Q(playerstatseason__season=current_season, playerstatseason__is_35man_roster=True)
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
            current_season = datetime.datetime.now().year
            if to_bool(carded):
                # Get carded players via PlayerStatSeason
                carded_player_ids = models.PlayerStatSeason.objects.filter(
                    season=current_season,
                    carded=True
                ).values_list('player_id', flat=True)
                query = query.filter(id__in=carded_player_ids)
            else:
                # Get non-carded players
                carded_player_ids = models.PlayerStatSeason.objects.filter(
                    season=current_season,
                    carded=True
                ).values_list('player_id', flat=True)
                query = query.exclude(id__in=carded_player_ids)
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


@csrf_exempt
def player_bulk_action(request):

    def _prep_url_param(param):
        if param.strip() == '':
            return None
        return param

    payload = {"players": []}


    # Get player list from bulk field
    if request.method == "POST":
        if request.POST.get("players", None):
            player_list = request.POST.get("players").split("\n")

            for raw_line in player_list:
                line = (raw_line or "").strip()
                if not line:
                    # Skip blank lines safely
                    continue

                # Prepare each object in the player list for processing
                if "\t" in line:
                    parts = [c.strip() for c in line.split("\t")]
                elif "," in line:
                    parts = [c.strip() for c in line.split(",")]
                else:
                    # If no delimiter detected, treat as a name-only row
                    parts = [line]

                # Pad or trim to exactly 8 fields expected by the API
                # name, position, mlbam_id, fg_id, ulmg_id, birthdate, school, draft_year
                if len(parts) < 8:
                    parts = parts + ([""] * (8 - len(parts)))
                else:
                    parts = parts[:8]

                name = _prep_url_param(parts[0])
                position = _prep_url_param(parts[1])
                mlbam_id = _prep_url_param(parts[2])
                fg_id = _prep_url_param(parts[3])
                ulmg_id = _prep_url_param(parts[4])
                birthdate_str = _prep_url_param(parts[5])
                school = _prep_url_param(parts[6])
                draft_year = _prep_url_param(parts[7])

                # Try to coerce birthdate into a proper date if provided
                birthdate = None
                if birthdate_str:
                    try:
                        # Accept common formats like YYYY-MM-DD, MM/DD/YYYY, etc.
                        from dateutil import parser as date_parser
                        birthdate = date_parser.parse(birthdate_str).date()
                    except Exception:
                        # Leave as None if parsing fails
                        birthdate = None

                ply = {
                    "name": name,
                    "position": position,
                    "mlbam_id": mlbam_id,
                    "fg_id": fg_id,
                    "birthdate": birthdate if birthdate else birthdate_str,
                    "school": school,
                    "ulmg_id": ulmg_id,
                    "draft_year": draft_year,
                    "created": False,
                }

                # Process each player
                # Find if this player exists via one of the IDs
                obj = None

                # try a ULMG ID if we are so lucky
                if not obj:
                    if ulmg_id:
                        try:
                            obj = models.Player.objects.get(id=ulmg_id)
                        except models.Player.DoesNotExist:
                            pass

                    # Many college players have FGIDs already
                    if not obj and fg_id:
                        try:
                            obj = models.Player.objects.get(fg_id=fg_id)
                        except models.Player.DoesNotExist:
                            pass

                    # Some HS and some college players have MLBAM IDs
                    if not obj and mlbam_id:
                        try:
                            obj = models.Player.objects.get(mlbam_id=mlbam_id)
                        except models.Player.DoesNotExist:
                            pass

                if not obj:
                    obj = models.Player(
                        name=name,
                        level="B",
                        is_prospect=True,
                        position=position,
                    )
                    # Update the JSON output we will return
                    ply["created"] = True

                # Update player object now that we have one
                try:
                    obj.level = "B"
                    obj.is_prospect = True
                    obj.position = position
                    obj.mlbam_id = mlbam_id
                    obj.fg_id = fg_id
                    obj.birthdate = birthdate
                    obj.school = school
                    obj.draft_year = draft_year
                    if not obj.amateur_seasons:
                        obj.amateur_seasons = []
                    if settings.CURRENT_SEASON not in (obj.amateur_seasons or []):
                        obj.amateur_seasons.append(settings.CURRENT_SEASON)
                    obj.save()
                    ply["ulmg_id"] = obj.id
                except Exception as e:
                    # Surface the error for this row but continue processing others
                    ply["error"] = f"save_failed: {e}"

                # Add this player to the payload for returning via JSON
                payload["players"].append(ply)

    # Return the payload
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


@csrf_exempt
def player_autocomplete(request):
    """
    API endpoint for player name autocomplete in navbar search
    Returns JSON list of players matching the search query
    """
    if request.method == "GET":
        query = request.GET.get("q", "").strip()
        
        if not query or len(query) < 2:
            return JsonResponse({"players": []})
        
        # Search for players by name, limit to 10 results for performance
        players = models.Player.objects.filter(
            name__icontains=query
        ).select_related('team').order_by(
            'last_name', 'first_name'
        )[:10]
        
        # Format results for autocomplete dropdown
        results = []
        for player in players:
            result = {
                "id": player.id,
                "name": player.name,
                "position": player.position,
                "level": player.level,
                "team": player.team.abbreviation if player.team else "FA",
                "url": f"/players/{player.id}/",
                "display": f"{player.name} ({player.position}) - {player.team.abbreviation if player.team else 'FA'}"
            }
            results.append(result)
        
        return JsonResponse({"players": results})
    
    return JsonResponse({"players": []})
