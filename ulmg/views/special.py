import csv
import datetime

from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import render, get_object_or_404
from django.db.models import Count, Avg, Sum, Max, Min, Q
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
        .order_by("-created")
    )
    context["no_birthdates"] = models.Player.objects.filter(
        birthdate__isnull=True
    ).order_by("-created")
    context["suspect_birthdates"] = models.Player.objects.filter(
        birthdate_qa=False, birthdate__day=1
    ).order_by("-birthdate")
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

    team_players = models.Player.objects.filter(team=context["team"])
    hitters = team_players.exclude(position="P").order_by(
        "position", "-level_order", "-is_carded", "last_name", "first_name"
    )
    pitchers = team_players.filter(position="P").order_by(
        "-level_order", "-is_carded", "last_name", "first_name"
    )
    context["35_roster_count"] = team_players.filter(is_35man_roster=True).count()
    context["mlb_roster_count"] = team_players.filter(
        is_mlb_roster=True, is_aaa_roster=False, is_reserve=False
    ).count()
    context["level_distribution"] = (
        team_players.order_by("level_order")
        .values("level_order")
        .annotate(Count("level_order"))
    )
    context["num_owned"] = models.Player.objects.filter(team=context["team"]).count()
    context["hitters"] = hitters
    context["pitchers"] = pitchers

    if request.user.is_superuser:
        context["own_team"] = True

    print(context["own_team"])

    return render(request, "team.html", context)
