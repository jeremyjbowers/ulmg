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

    # AA draft metadata - always offseason, use settings to determine year
    # If we're in midseason, next draft is CURRENT_SEASON + 1 offseason
    # If we're in offseason, current draft is CURRENT_SEASON offseason
    draft_year = settings.CURRENT_SEASON
    if settings.CURRENT_SEASON_TYPE == "midseason":
        draft_year = settings.CURRENT_SEASON + 1
    
    context['draft_type'] = "aa"
    context['draft_year'] = draft_year
    context['draft_season'] = "offseason"

    context["team"] = get_object_or_404(models.Team, owner_obj=context["owner"])
    context["wishlist"] = models.Wishlist.objects.get(owner=context["owner"])

    context['my_aa_picks'] = models.DraftPick.objects.filter(team=context['team'], year=str(draft_year), season="offseason", draft_type="aa")
    context['all_aa_picks'] = models.DraftPick.objects.filter(year=str(draft_year), season="offseason", draft_type="aa").values('overall_pick_number', 'team__abbreviation')
 
    # Flag for templates to customize wishlist controls
    context['wishlist_draft_view'] = True

    # Get current season for PlayerStatSeason queries
    season = settings.CURRENT_SEASON

    # All AA-eligible wishlist players for this owner
    # Prefetch PlayerStatSeason data to avoid N+1 queries and ensure we use current stats
    base_qs = models.WishlistPlayer.objects.filter(
        wishlist=context["wishlist"], player__team__isnull=True, player__level="B"
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


@login_required
def my_draft_prep(request, list_type):
    context = utils.build_context(request)

    # Open draft metadata - use settings and list_type to determine draft year and season
    # list_type determines which draft we're preparing for (offseason or midseason)
    if list_type == "offseason":
        # Offseason draft: if we're in midseason, next draft is CURRENT_SEASON + 1 offseason
        # If we're in offseason, current draft is CURRENT_SEASON offseason
        draft_year = settings.CURRENT_SEASON
        if settings.CURRENT_SEASON_TYPE == "midseason":
            draft_year = settings.CURRENT_SEASON + 1
        draft_season = "offseason"
    elif list_type == "midseason":
        # Midseason draft: always CURRENT_SEASON midseason
        draft_year = settings.CURRENT_SEASON
        draft_season = "midseason"
    else:
        # Default fallback
        draft_year = settings.CURRENT_SEASON
        draft_season = settings.CURRENT_SEASON_TYPE

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

    if list_type == "offseason":
        base_qs = models.WishlistPlayer.objects.filter(
            wishlist=context["wishlist"],
            player__team__isnull=True,
            player__level__in=["A", "V"],
        ).select_related('player').prefetch_related(prefetch_stats).order_by("rank")

    elif list_type == "midseason":
        # For midseason drafts, filter by players carded in the previous season
        # Use CURRENT_SEASON - 1 to get the previous carded season
        previous_season = settings.CURRENT_SEASON - 1
        base_qs = models.WishlistPlayer.objects.filter(
            wishlist=context["wishlist"],
            player__team__isnull=True,
            player__carded_seasons__contains=[previous_season],
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
