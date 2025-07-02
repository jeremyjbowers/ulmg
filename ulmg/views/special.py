import csv
import datetime

from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import render, get_object_or_404
from django.db.models import Count, Avg, Sum, Max, Min, Q, Case, When, IntegerField
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.http import JsonResponse
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.models import User
import ujson as json

from ulmg import models, utils


@staff_member_required
@login_required
def special_bulk_add_players(request):
    context = utils.build_context(request)

    return render(request, "special_bulk_add.html", context)


@staff_member_required
@login_required
def player_util(request):
    context = utils.build_context(request)
    context["no_ids"] = (
        models.Player.objects.filter(
            fg_id__isnull=True, bref_id__isnull=True, mlbam_id__isnull=True
        )
        .filter(is_amateur=False)
        .annotate(
            team_order=Case(
                When(team__isnull=True, then=1),
                default=0,
                output_field=IntegerField()
            )
        )
        .order_by("team_order", "-created")
    )
    context["no_birthdates"] = models.Player.objects.filter(
        birthdate__isnull=True
    ).annotate(
        team_order=Case(
            When(team__isnull=True, then=1),
            default=0,
            output_field=IntegerField()
        )
    ).order_by("team_order", "-created")
    context["suspect_birthdates"] = models.Player.objects.filter(
        birthdate_qa=False, birthdate__day=1
    ).annotate(
        team_order=Case(
            When(team__isnull=True, then=1),
            default=0,
            output_field=IntegerField()
        )
    ).order_by("team_order", "-birthdate")
    return render(request, "player_util.html", context)


@staff_member_required
@login_required
def trade_util(request):
    if request.method == "GET":
        context = utils.build_context(request)
        context["hitters"] = models.Player.objects.filter(is_owned=True).exclude(
            position="P"
        )
        context["pitchers"] = models.Player.objects.filter(is_owned=True, position="P")
        context["picks"] = models.DraftPick.objects.filter(
            year__gte=settings.CURRENT_SEASON
        ).exclude(player__isnull=False)
        return render(request, "trade_form.html", context)

    if request.method == "POST":
        payload = {}
        return JsonResponse(payload, safe=False)


@staff_member_required
@login_required
def my_team(request, abbreviation):
    context = utils.build_context(request)
    context["team"] = get_object_or_404(
        models.Team, abbreviation__icontains=abbreviation
    )
    context["owner"] = context["team"].owner

    # Get team players for roster counts and distribution (still need Player objects for this)
    team_players = models.Player.objects.filter(team=context["team"])
    context["35_roster_count"] = team_players.filter(is_35man_roster=True).count()
    context["mlb_roster_count"] = team_players.filter(
        is_mlb_roster=True, is_aaa_roster=False, is_reserve=False
    ).count()
    context["level_distribution"] = (
        team_players.order_by("level_order")
        .values("level_order")
        .annotate(Count("level_order"))
    )
    context["num_owned"] = team_players.count()

    # Use PlayerStatSeason for displaying roster with current season stats (2025)
    current_season = 2025
    team_stat_seasons = models.PlayerStatSeason.objects.filter(
        player__team=context["team"], 
        season=current_season
    ).select_related('player')
    
    # Split into hitters and pitchers using PlayerStatSeason objects
    hitters = team_stat_seasons.exclude(player__position="P").order_by(
        "player__position", "-player__level_order", "-player__is_carded", 
        "player__last_name", "player__first_name"
    )
    pitchers = team_stat_seasons.filter(player__position="P").order_by(
        "-player__level_order", "-player__is_carded", 
        "player__last_name", "player__first_name"
    )

    context["hitters"] = hitters
    context["pitchers"] = pitchers

    if request.user.is_superuser:
        context["own_team"] = True

    print(context["own_team"])

    return render(request, "team.html", context)
