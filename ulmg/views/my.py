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

    # AA draft metadata
    context['draft_type'] = "aa"
    context['draft_year'] = 2025
    context['draft_season'] = "offseason"

    context["team"] = get_object_or_404(models.Team, owner_obj=context["owner"])
    context["wishlist"] = models.Wishlist.objects.get(owner=context["owner"])

    context['my_aa_picks'] = models.DraftPick.objects.filter(team=context['team'], year=2025, season="offseason", draft_type="aa")
    context['all_aa_picks'] = models.DraftPick.objects.filter(year=2025, season="offseason", draft_type="aa").values('overall_pick_number', 'team__abbreviation')
 
    # Flag for templates to customize wishlist controls
    context['wishlist_draft_view'] = True

    # All AA-eligible wishlist players for this owner
    base_qs = models.WishlistPlayer.objects.filter(
        wishlist=context["wishlist"], player__team__isnull=True, player__level="B"
    ).order_by("rank")

    # Keep flat list for any legacy uses
    context["players"] = base_qs

    # Prepare players grouped by tier for the tier board UI
    tiers = []
    for tier_num in range(1, 6):
        tiers.append(
            {
                "id": tier_num,
                "label": f"Tier {tier_num}",
                "players": base_qs.filter(tier=tier_num).order_by("rank", "player__last_name"),
            }
        )

    # Players without an assigned tier (or outside our 1-5 board) go into an "Unassigned" bucket
    context["untiered_players"] = base_qs.filter(
        Q(tier__isnull=True) | Q(tier__lt=1) | Q(tier__gt=5)
    ).order_by("rank", "player__last_name")
    context["tiers"] = tiers

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

    # Open draft metadata
    context['draft_type'] = "open"
    context['draft_year'] = 2025
    context['draft_season'] = "midseason"

    context["team"] = get_object_or_404(models.Team, owner_obj=context["owner"])
    context['wishlist_draft_view'] = True
    context["wishlist"] = models.Wishlist.objects.get(owner=context["owner"])

    context['my_picks'] = [p.overall_pick_number for p in models.DraftPick.objects.filter(team=context['team'], year=2025, season="midseason", draft_type="open")]
    context['all_picks'] = models.DraftPick.objects.filter(year=2025, season="midseason", draft_type="open").values('overall_pick_number', 'team__abbreviation')
 
    context['players'] = []

    if list_type == "offseason":
        base_qs = models.WishlistPlayer.objects.filter(
            wishlist=context["wishlist"],
            player__team__isnull=True,
            player__level__in=["A", "V"],
        ).order_by("rank")

    elif list_type == "midseason":
        base_qs = models.WishlistPlayer.objects.filter(
            wishlist=context["wishlist"],
            player__team__isnull=True,
            player__carded_seasons__contains=[2024],
        ).order_by("rank")
    else:
        base_qs = models.WishlistPlayer.objects.none()

    # Keep flat list for any legacy uses
    context["players"] = base_qs

    # Prepare players grouped by tier for the tier board UI (reuse same 5 tiers)
    tiers = []
    for tier_num in range(1, 6):
        tiers.append(
            {
                "id": tier_num,
                "label": f"Tier {tier_num}",
                "players": base_qs.filter(tier=tier_num).order_by("rank", "player__last_name"),
            }
        )

    context["untiered_players"] = base_qs.filter(
        Q(tier__isnull=True) | Q(tier__lt=1) | Q(tier__gt=5)
    ).order_by("rank", "player__last_name")
    context["tiers"] = tiers

    context["tags"] = set()

    for p in context["players"].values("tags"):
        if p["tags"]:
            for z in p["tags"]:
                context["tags"].add(z)

    context["tags"] = sorted(list(context["tags"]), key=lambda x: x)
    context["num_owned"] = models.Player.objects.filter(team=context["team"]).count()

    return render(request, "my/wishlist_beta.html", context)
