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
def my_wishlist_beta(request):
    context = utils.build_context(request)

    context['draft_type'] = "aa"

    context["team"] = get_object_or_404(models.Team, owner_obj=context["owner"])
    context["wishlist"] = models.Wishlist.objects.get(owner=context["owner"])

    context['my_aa_picks'] = models.DraftPick.objects.filter(team=context['team'], year=2025, season="offseason", draft_type="aa")
    context['all_aa_picks'] = models.DraftPick.objects.filter(year=2025, season="offseason", draft_type="aa").values('overall_pick_number', 'team__abbreviation')
 
    context["players"] = models.WishlistPlayer.objects.filter(
        wishlist=context["wishlist"], player__is_owned=False, player__level="B"
    ).order_by("rank")

    context["tags"] = set()

    for p in context["players"].values("tags"):
        if p["tags"]:
            for z in p["tags"]:
                context["tags"].add(z)

    context["tags"] = sorted(list(context["tags"]), key=lambda x: x)
    context["num_owned"] = models.Player.objects.filter(team=context["team"]).count()

    return render(request, "my/wishlist_beta.html", context)


@login_required
def my_draft_prep(request, list_type):
    context = utils.build_context(request)

    context['draft_type'] = "open"

    context["team"] = get_object_or_404(models.Team, owner_obj=context["owner"])
    context["wishlist"] = models.Wishlist.objects.get(owner=context["owner"])

    context['my_picks'] = models.DraftPick.objects.filter(team=context['team'], year=2025, season="offseason", draft_type="open")
    context['all_picks'] = models.DraftPick.objects.filter(year=2025, season="offseason", draft_type="open").values('overall_pick_number', 'team__abbreviation')
 
    context['players'] = []
 
    if list_type == "offseason":    
        context["players"] = models.WishlistPlayer.objects.filter(
            wishlist=context["wishlist"], player__is_owned=False, player__level__in=["A","V"]
        ).order_by("rank")

    if list_type == "midseason":
        context["players"] = models.WishlistPlayer.objects.filter(
            wishlist=context["wishlist"], player__is_owned=False, player__is_carded=True
        ).order_by("rank") 

    context["tags"] = set()

    for p in context["players"].values("tags"):
        if p["tags"]:
            for z in p["tags"]:
                context["tags"].add(z)

    context["tags"] = sorted(list(context["tags"]), key=lambda x: x)
    context["num_owned"] = models.Player.objects.filter(team=context["team"]).count()

    return render(request, "my/wishlist_beta.html", context)
