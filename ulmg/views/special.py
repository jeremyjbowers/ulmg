import csv
import datetime

from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.shortcuts import render, get_object_or_404, redirect
from django.db.models import Count, Avg, Sum, Max, Min, Q, Case, When, IntegerField
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.http import JsonResponse
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.models import User
from django.contrib import messages
import ujson as json

from ulmg import models, utils
from ulmg.duplicate_merge import merge_delete_stub, mark_not_duplicate, player_info_dict


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
        .annotate(
            team_order=Case(
                When(team__isnull=True, then=1),
                default=0,
                output_field=IntegerField(),
            )
        )
        .order_by("team_order", "-created")
    )

    context["no_birthdates"] = (
        models.Player.objects.filter(birthdate__isnull=True)
        .annotate(
            team_order=Case(
                When(team__isnull=True, then=1),
                default=0,
                output_field=IntegerField(),
            )
        )
        .order_by("team_order", "-created")
    )

    context["suspect_birthdates"] = (
        models.Player.objects.filter(birthdate_qa=False, birthdate__day=1)
        .annotate(
            team_order=Case(
                When(team__isnull=True, then=1),
                default=0,
                output_field=IntegerField(),
            )
        )
        .order_by("team_order", "-birthdate")
    )

    current_season = settings.CURRENT_SEASON

    # Players whose last non‑NPB/KBO stat season was two years ago,
    # and who have no NPB/KBO seasons at all.
    context["possibly_retired"] = (
        models.Player.objects
        .annotate(
            last_stat_season=Max(
                "playerstatseason__season",
                filter=Q(
                    playerstatseason__classification__in=[
                        "1-mlb",      # MLB
                        "2-milb",     # MiLB
                        "5-college",  # college/amateur
                    ]
                ),
            )
        )
        .filter(last_stat_season=current_season - 2)
        .exclude(playerstatseason__classification__in=["3-npb", "4-kbo"])
        .annotate(
            team_order=Case(
                When(team__isnull=True, then=1),
                default=0,
                output_field=IntegerField(),
            )
        )
        .order_by("team_order", "-last_stat_season", "last_name", "first_name")
    )

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

    # Get current season for PlayerStatSeason queries
    current_season = utils.get_current_season()

    # Get team players for roster counts and distribution
    team_players = models.Player.objects.filter(team=context["team"])
    
    # Count roster statuses using PlayerStatSeason (is_ulmg35man_roster)
    context["35_roster_count"] = models.PlayerStatSeason.objects.filter(
        player__team=context["team"], 
        season=current_season,
        is_ulmg35man_roster=True
    ).count()
    
    context["mlb_roster_count"] = models.PlayerStatSeason.objects.filter(
        player__team=context["team"],
        season=current_season,
        is_ulmg_mlb_roster=True, 
        is_ulmg_aaa_roster=False,
        player__is_ulmg_reserve=False
    ).count()
    
    context["level_distribution"] = (
        team_players.order_by("level_order")
        .values("level_order")
        .annotate(Count("level_order"))
    )
    context["num_owned"] = team_players.count()

    # Query for players directly instead of PlayerStatSeason objects
    # Split into hitters and pitchers using Player objects
    hitters = team_players.exclude(position="P").order_by(
        "position", "-level_order", "last_name", "first_name"
    )
    pitchers = team_players.filter(position="P").order_by(
        "-level_order", "last_name", "first_name"
    )

    context["hitters"] = hitters
    context["pitchers"] = pitchers

    if request.user.is_superuser:
        context["own_team"] = True

    print(context["own_team"])

    return render(request, "team.html", context)


@staff_member_required
@login_required
def duplicate_players_list(request):
    """List pending duplicate player candidates for admin review."""
    context = utils.build_context(request)
    pending = models.DuplicatePlayerCandidate.objects.filter(
        status=models.DuplicatePlayerCandidate.PENDING
    ).select_related("player1", "player2").order_by("-created")

    context["candidates"] = []
    for c in pending:
        context["candidates"].append({
            "candidate": c,
            "player1_info": player_info_dict(c.player1),
            "player2_info": player_info_dict(c.player2),
        })

    return render(request, "duplicate_players_list.html", context)


@staff_member_required
@login_required
@require_http_methods(["GET", "POST"])
def duplicate_players_detail(request, candidate_id):
    """Detail view for a duplicate candidate with merge/not-duplicate actions."""
    candidate = get_object_or_404(
        models.DuplicatePlayerCandidate,
        id=candidate_id,
        status=models.DuplicatePlayerCandidate.PENDING,
    )
    context = utils.build_context(request)
    context["candidate"] = candidate
    context["player1_info"] = player_info_dict(candidate.player1)
    context["player2_info"] = player_info_dict(candidate.player2)

    if request.method == "POST":
        action = request.POST.get("action")
        keep_id = request.POST.get("keep_id")
        delete_id = request.POST.get("delete_id")

        if action == "not_duplicate":
            ok, msg = mark_not_duplicate(candidate, user=request.user)
            if ok:
                messages.success(request, msg)
            else:
                messages.error(request, msg)
            return redirect("duplicate_players_list")

        if action == "merge" and keep_id and delete_id:
            try:
                keep_player = models.Player.objects.get(id=int(keep_id))
                delete_player = models.Player.objects.get(id=int(delete_id))
            except (models.Player.DoesNotExist, ValueError):
                messages.error(request, "Invalid player selection.")
                return render(request, "duplicate_players_detail.html", context)

            if keep_player.id not in (candidate.player1_id, candidate.player2_id):
                messages.error(request, "Selected keeper is not in this pair.")
                return render(request, "duplicate_players_detail.html", context)
            if delete_player.id not in (candidate.player1_id, candidate.player2_id):
                messages.error(request, "Selected delete target is not in this pair.")
                return render(request, "duplicate_players_detail.html", context)

            ok, msg = merge_delete_stub(
                keep_player, delete_player,
                user=request.user, candidate=candidate
            )
            if ok:
                messages.success(request, msg)
            else:
                messages.error(request, msg)
            return redirect("duplicate_players_list")

        messages.error(request, "Invalid action.")
        return render(request, "duplicate_players_detail.html", context)

    return render(request, "duplicate_players_detail.html", context)
