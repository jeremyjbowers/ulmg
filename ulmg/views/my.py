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
from django.contrib.auth.models import User
import ujson as json

from ulmg import models, utils

@login_required
def my_team(request):
    context = utils.build_context(request)
    owner = models.Owner.objects.get(user=request.user)
    context["team"] = get_object_or_404(
        models.Team, owner_obj=owner
    )
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
    return render(request, "my/team.html", context)


@login_required
def my_team_other(request):
    context = utils.build_context(request)
    owner = models.Owner.objects.get(user=request.user)
    team = get_object_or_404(
        models.Team, owner_obj=owner
    )
    context["team"] = team
    team_players = models.Player.objects.filter(team=context["team"])
    context["level_distribution"] = (
        team_players.order_by("level_order")
        .values("level_order")
        .annotate(Count("level_order"))
    )
    context["num_owned"] = models.Player.objects.filter(team=team).count()
    context["trades"] = models.TradeReceipt.objects.filter(
        team=team, trade__isnull=False
    ).order_by("-trade__date")
    context["picks"] = models.DraftPick.objects.filter(team=team).order_by(
        "-year", "season", "draft_type", "draft_round", "pick_number"
    )
    return render(request, "my/team_other.html", context)