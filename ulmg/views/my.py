import csv
import datetime
import itertools
from django.db.models.expressions import OrderBy

from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import render, get_object_or_404, redirect
from django.db.models import Count, Avg, Sum, Max, Min, Q
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.http import JsonResponse
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
import ujson as json

from ulmg import models, utils


@login_required
def my_lineup(request):
    context = utils.build_context(request)

    owner = models.Owner.objects.get(user=request.user)

    team = get_object_or_404(models.Team, owner_obj=context["owner"])

    context["team"] = team

    context['lineup'], created = models.Lineup.objects.get_or_create(team=context['team'], season=utils.get_current_season())
    context['lineup_slots'] = models.LineupSlot.objects.filter(lineup=context['lineup'])

    team_players = models.Player.objects.filter(team=context["team"])

    hitters = team_players.filter(stats__2021_majors__plate_appearances__gte=0).exclude(position="P").order_by(
        "position", "-level_order", "-is_carded", "last_name", "first_name"
    )

    pitchers = team_players.filter(position="P", stats__2021_majors__g__gte=0).order_by(
        "-level_order", "-is_carded", "last_name", "first_name"
    )

    context['offense'] = {}

    positions = ["C", "1B", "2B", "3B", "SS", "RF", "CF", "LF", "DH"]

    for h in hitters:
        if not h.defense:
            h.defense += ["DH-0-0"]

        for d in h.defense:
            pos = d.split('-')[0].lower()
            rating = d.split('-')[2]

            if not context['offense'].get(f"hit_{pos}", None):
                context['offense'][f"hit_{pos}"] = []

            payload = {
                "player": h,
                "position": pos,
                "rating": rating,
                "name": h.name,
                "value": h.strat_obtb_tot,
                "pa": h.stats['2021_majors']['plate_appearances']
            }

            context['offense'][f"hit_{pos}"].append(payload)
            context['offense'][f"hit_{pos}"] = sorted(context['offense'][f"hit_{pos}"], key=lambda x: x['rating'])

    return render(request, "my/lineups.html", context)


@login_required
def my_team(request):
    context = utils.build_context(request)
    # context["team"] = get_object_or_404(models.Team, owner_obj=context["owner"])
    # team_players = models.Player.objects.filter(team=context["team"])
    # hitters = team_players.exclude(position="P").order_by(
    #     "position", "-level_order", "-is_carded", "last_name", "first_name"
    # )
    # pitchers = team_players.filter(position="P").order_by(
    #     "-level_order", "-is_carded", "last_name", "first_name"
    # )

    # position_groups = (
    #     team_players.exclude(position="P")
    #         .order_by('position')
    #         .values('position')
    #         .annotate(Count('position'))
    # )

    # carded_pa = (
    #     team_players.exclude(position="P").filter(is_carded=True)
    #         .order_by('position')
    #         .values('position')
    #         .annotate(Sum('py_plate_appearances'))
    # )
    # carded_positions = [x['position'] for x in carded_pa]

    # current_pa = (
    #     team_players.exclude(position="P").filter(ls_is_mlb=True)
    #         .order_by('position')
    #         .values('position')
    #         .annotate(Sum('ls_plate_appearances'))
    # )

    # current_positions = [x['position'] for x in current_pa]

    # for pos in position_groups:
    #     pos['carded_pa'] = carded_pa[carded_positions.index(pos['position'])]['py_plate_appearances__sum']
    #     pos['current_pa'] = current_pa[current_positions.index(pos['position'])]['ls_plate_appearances__sum']

    # context["35_roster_count"] = team_players.filter(is_35man_roster=True).count()
    # context["mlb_roster_count"] = team_players.filter(
    #     is_mlb_roster=True, is_aaa_roster=False, is_reserve=False
    # ).count()
    # context["level_distribution"] = (
    #     team_players.order_by("level_order")
    #     .values("level_order")
    #     .annotate(Count("level_order"))
    # )
    # context["num_owned"] = models.Player.objects.filter(team=context["team"]).count()
    # context["hitters"] = hitters
    # context["pitchers"] = pitchers
    # context["combined_pa"] = position_groups
    # return render(request, "my/team.html", context)
    team = get_object_or_404(models.Team, owner_obj=context["owner"])
    return redirect(f"/teams/{ team.abbreviation }/")


@login_required
def my_wishlist(request, list_type):
    context = utils.build_context(request)
    context["team"] = get_object_or_404(models.Team, owner_obj=context["owner"])
    context["list_type"] = list_type

    context["aa_hitters"] = []
    context["aa_pitchers"] = []
    context["op_hitters"] = []
    context["op_pitchers"] = []
    context["hitters"] = []
    context["pitchers"] = []

    if list_type == "draft":
        for p in models.WishlistPlayer.objects.filter(wishlist=context["wishlist"]):
            if not p.player.is_owned:
                if p.player.level == "B":
                    if p.player.position == "P":
                        context["aa_pitchers"].append(p)
                    else:
                        context["aa_hitters"].append(p)
                else:
                    if p.player.position == "P":
                        context["op_pitchers"].append(p)
                    else:
                        context["op_hitters"].append(p)
        try:
            context["aa_hitters"] = sorted(
                context["aa_hitters"], key=lambda x: (x.tier, x.rank)
            )
        except:
            pass

        try:
            context["aa_pitchers"] = sorted(
                context["aa_pitchers"], key=lambda x: (x.tier, x.rank)
            )
        except:
            pass

        context["op_hitters"] = sorted(context["op_hitters"], key=lambda x: (x.tier, x.rank))
        context["op_pitchers"] = sorted(context["op_pitchers"], key=lambda x: (x.tier, x.rank))

    if list_type == "trade":
        for p in models.WishlistPlayer.objects.filter(wishlist=context["wishlist"]):
            if p.player.is_owned and p.player.team != context["team"]:
                if p.player.position == "P":
                    context["pitchers"].append(p)
                else:
                    context["hitters"].append(p)

        context["hitters"] = sorted(context["hitters"], key=lambda x: (x.tier, x.rank))
        context["pitchers"] = sorted(
            context["pitchers"], key=lambda x: (x.tier, x.rank)
        )

    return render(request, "my/wishlist.html", context)


@login_required
def my_draftlist(request):
    context = utils.build_context(request)
    context["team"] = get_object_or_404(models.Team, owner_obj=context["owner"])

    context["aa_hitters"] = []
    context["aa_pitchers"] = []
    context["op_hitters"] = []
    context["op_pitchers"] = []

    for p in models.WishlistPlayer.objects.filter(wishlist=context["wishlist"]):
        if not p.player.is_owned:
            if p.player.level == "B":
                if p.player.position == "P":
                    context["aa_pitchers"].append(p)
                else:
                    context["aa_hitters"].append(p)
            else:
                if p.player.position == "P":
                    context["op_pitchers"].append(p)
                else:
                    context["op_hitters"].append(p)
    try:
        context["aa_hitters"] = sorted(
            context["aa_hitters"], key=lambda x: (x.tier, x.rank)
        )
    except:
        pass

    try:
        context["aa_pitchers"] = sorted(
            context["aa_pitchers"], key=lambda x: (x.tier, x.rank)
        )
    except:
        pass

    context["op_hitters"] = sorted(context["op_hitters"], key=lambda x: (x.tier, x.rank))
    context["op_pitchers"] = sorted(context["op_pitchers"], key=lambda x: (x.tier, x.rank))

    return render(request, "my/draft_prep.html", context)
