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
def my_team(request):
    context = utils.build_context(request)
    team = get_object_or_404(models.Team, owner_obj=context["owner"])
    return redirect(f"/teams/{ team.abbreviation }/")

@login_required
def my_draft_prep(request):
    context = utils.build_context(request)

    context["team"] = get_object_or_404(models.Team, owner_obj=context["owner"])
    context["wishlist"] = models.Wishlist.objects.get(owner=context["owner"])

    context['my_open_picks'] = models.DraftPick.objects.filter(team=context['team'], year=2025, season="offseason", draft_type="open")
    context['all_open_picks'] = models.DraftPick.objects.filter(year=2025, season="offseason", draft_type="open").values('overall_pick_number', 'team__abbreviation')
 
    context["players"] = models.WishlistPlayer.objects.filter(
        wishlist=context["wishlist"], player__is_owned=False, player__level__in=["A","V"]
    ).order_by("rank")

    context["tags"] = set()

    for p in context["players"].values("tags"):
        if p["tags"]:
            for z in p["tags"]:
                context["tags"].add(z)

    context["tags"] = sorted(list(context["tags"]), key=lambda x: x)
    context["num_owned"] = models.Player.objects.filter(team=context["team"]).count()

    return render(request, "my/draft_prep.html", context)


@login_required
def my_wishlist(request, list_type):
    context = utils.build_context(request)
    context["team"] = get_object_or_404(models.Team, owner_obj=context["owner"])
    context["list_type"] = list_type
    context['wishlist'] = models.Wishlist.objects.get(owner=context['owner'])
    context["aa_hitters"] = []
    context["aa_pitchers"] = []
    context["op_hitters"] = []
    context["op_pitchers"] = []
    context["hitters"] = []
    context["pitchers"] = []

    if list_type == "draft":
        for p in models.WishlistPlayer.objects.filter(wishlist=context["wishlist"]):
            if not p.tier:
                p.tier = 6
            if not p.rank:
                p.rank = 999

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

        context["op_hitters"] = sorted(
            context["op_hitters"], key=lambda x: (x.tier, x.rank)
        )
        context["op_pitchers"] = sorted(
            context["op_pitchers"], key=lambda x: (x.tier, x.rank)
        )

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
def my_wishlist_beta(request):
    context = utils.build_context(request)
    context["team"] = get_object_or_404(models.Team, owner_obj=context["owner"])
    context['wishlist'] = models.Wishlist.objects.get(owner=context['owner'])

    context["aa_hitters"] = []
    context["aa_pitchers"] = []

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

    context["op_hitters"] = sorted(
        context["op_hitters"], key=lambda x: (x.tier, x.rank)
    )
    context["op_pitchers"] = sorted(
        context["op_pitchers"], key=lambda x: (x.tier, x.rank)
    )

    return render(request, "my/draft_prep.html", context)

@login_required
def my_midseason_draft(request):
    context = utils.build_context(request)
    context["team"] = get_object_or_404(models.Team, owner_obj=context["owner"])
    context['wishlist'] = models.Wishlist.objects.get(owner=context['owner'])
    context["num_owned"] = models.Player.objects.filter(team=context["team"]).count()

    if request.user.is_authenticated:
        owner = models.Owner.objects.get(user=request.user)
        if owner.team() == context["team"]:
            context["own_team"] = True
        else:
            context["own_team"] = False
    else:
        context["own_team"] = False

    context["op_hitters"] = models.WishlistPlayer.objects\
    .filter(wishlist=context["wishlist"])\
    .exclude(player__position="P")\
    .filter(
        Q(player__team__isnull=True, player__stats__2024_majors_hit__plate_appearances__gte=1)
        | Q(
            player__level="V",
            player__is_owned=True,
            player__is_mlb_roster=False,
            player__is_1h_c=False,
            player__is_1h_pos=False,
            player__is_reserve=False,
        )
    )

    context["op_pitchers"] = models.WishlistPlayer.objects\
    .filter(wishlist=context["wishlist"])\
    .filter(
        Q(player__team__isnull=True, player__stats__2024_majors_pitch__ip__gte=1, player__position__icontains="P")
        | Q(
            player__level="V",
            player__position="P",
            player__is_owned=True,
            player__is_mlb_roster=False,
            player__is_1h_p=False,
            player__is_reserve=False,
        )
    )

    # context['op_hitters'] = models.WishlistPlayer.objects.exclude(player__position="P").filter(wishlist=context["wishlist"], player__is_owned=False, player__stats__2024_majors_hit__plate_appearances__gte=1)

    # context['op_pitchers'] = models.WishlistPlayer.objects.filter(player__position="P", wishlist=context["wishlist"], player__is_owned=False, player__stats__2024_majors_pitch__g__gte=1)

    context['aa_hitters'] = models.WishlistPlayer.objects.exclude(player__position="P").filter(wishlist=context["wishlist"], player__is_owned=False, player__is_carded=False, player__level="B")

    context['aa_pitchers'] = models.WishlistPlayer.objects.filter(player__position="P", wishlist=context["wishlist"], player__is_owned=False, player__is_carded=False, player__level="B")

    context["op_hitters"] = sorted(
        context["op_hitters"], key=lambda x: (x.tier, x.rank)
    )
    context["op_pitchers"] = sorted(
        context["op_pitchers"], key=lambda x: (x.tier, x.rank)
    )

    context["aa_hitters"] = sorted(
        context["aa_hitters"], key=lambda x: (x.tier, x.rank)
    )
    context["aa_pitchers"] = sorted(
        context["aa_pitchers"], key=lambda x: (x.tier, x.rank)
    )

    return render(request, "my/midseason_draft_prep.html", context)
