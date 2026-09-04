# ABOUTME: Owner-facing views for team home, AA draft prep, and Open draft prep wishlists.
# ABOUTME: Draft-prep lists follow offseason/midseason eligibility (AA is B-only; Open varies).
import csv
import datetime
import itertools
from django.db.models.expressions import OrderBy

from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import render, get_object_or_404, redirect
from django.db.models import Count, Avg, Sum, Max, Min, Q, Prefetch
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.http import JsonResponse
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.views.decorators.cache import never_cache
import ujson as json

from ulmg import models, utils


@never_cache
@login_required
def my_team(request):
    context = utils.build_context(request)
    team = get_object_or_404(models.Team, owner_obj=context["owner"])
    return redirect(f"/teams/{ team.abbreviation }/")


@never_cache
@login_required
def my_wishlist_beta(request):
    context = utils.build_context(request)

    draft_year, draft_season = utils.get_draft_prep_year_season(
        "aa", list_type=utils.get_draft_prep_season_type()
    )

    context['draft_type'] = "aa"
    context['draft_year'] = draft_year
    context['draft_season'] = draft_season

    context["team"] = get_object_or_404(models.Team, owner_obj=context["owner"])
    context["wishlist"] = models.Wishlist.objects.get(owner=context["owner"])

    context['my_aa_picks'] = models.DraftPick.objects.filter(
        team=context['team'], year=str(draft_year), season=draft_season, draft_type="aa"
    )
    context['all_aa_picks'] = models.DraftPick.objects.filter(
        year=str(draft_year), season=draft_season, draft_type="aa"
    ).values('overall_pick_number', 'team__abbreviation')
 
    # Flag for templates to customize wishlist controls
    context['wishlist_draft_view'] = True

    # Get current season for PlayerStatSeason queries
    season = settings.CURRENT_SEASON

    # Prefetch PlayerStatSeason data to avoid N+1 queries and ensure we use current stats
    # Exclude owned players (player__team__isnull=True) - players disappear when drafted
    player_filters = {
        f"player__{key}": value
        for key, value in utils.get_draft_prep_player_filters("aa", list_type=draft_season).items()
    }
    base_qs = models.WishlistPlayer.objects.filter(
        wishlist=context["wishlist"],
        **player_filters,
    ).select_related('player').prefetch_related(
        Prefetch(
            'player__playerstatseason_set',
            queryset=models.PlayerStatSeason.objects.filter(is_career=False).order_by('-season', 'classification'),
            to_attr='all_stat_seasons'
        )
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


@never_cache
@login_required
def my_draft_prep(request, list_type):
    context = utils.build_context(request)

    draft_year, draft_season = utils.get_draft_prep_year_season("open", list_type=list_type)

    context['draft_type'] = "open"
    context['draft_year'] = draft_year
    context['draft_season'] = draft_season

    context["team"] = get_object_or_404(models.Team, owner_obj=context["owner"])
    context['wishlist_draft_view'] = True
    context["wishlist"] = models.Wishlist.objects.get(owner=context["owner"])

    context['my_picks'] = [p.overall_pick_number for p in models.DraftPick.objects.filter(team=context['team'], year=str(draft_year), season=draft_season, draft_type="open")]
    context['all_picks'] = models.DraftPick.objects.filter(year=str(draft_year), season=draft_season, draft_type="open").values('overall_pick_number', 'team__abbreviation')
 
    # Get current season for PlayerStatSeason queries
    season = settings.CURRENT_SEASON

    context['players'] = []

    # Prefetch PlayerStatSeason data to avoid N+1 queries and ensure we use current stats
    prefetch_stats = Prefetch(
        'player__playerstatseason_set',
        queryset=models.PlayerStatSeason.objects.filter(is_career=False).order_by('-season', 'classification'),
        to_attr='all_stat_seasons'
    )

    if list_type in ("offseason", "midseason"):
        if list_type == "midseason":
            context["open_carded_season"] = utils.get_midseason_open_carded_season(draft_year)
        player_filters = {
            f"player__{key}": value
            for key, value in utils.get_draft_prep_player_filters("open", list_type=list_type).items()
        }
        base_qs = models.WishlistPlayer.objects.filter(
            wishlist=context["wishlist"],
            **player_filters,
        ).select_related('player').prefetch_related(prefetch_stats).order_by("rank")
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
