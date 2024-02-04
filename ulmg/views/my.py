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
    context['wishlist'] = models.Wishlist.objects.get(owner=context['owner'])
    context["aa_hitters"] = []
    context["aa_pitchers"] = []
    context["op_hitters"] = []
    context["op_pitchers"] = []

    for p in models.WishlistPlayer.objects.filter(wishlist=context["wishlist"]):
        if not p.tier:
            p.tier = 6
        if not p.rank:
            p.rank = 999

        if not p.player.is_owned:
            if p.player.level in ["A", "V"]:
                if p.player.position == "P":
                    context['op_pitchers'].append(p)

                else:
                    context['op_hitters'].append(p)

            if p.player.level == "B":
                if p.player.position == "P":
                    context["aa_pitchers"].append(p)
                else:
                    context["aa_hitters"].append(p)                  

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
def my_draftlist(request):
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
