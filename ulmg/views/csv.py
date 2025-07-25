import csv
import datetime

from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import render, get_object_or_404
from django.db.models import Count, Avg, Sum, Max, Min, Q
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.http import JsonResponse
from django.conf import settings
import ujson as json

from ulmg import models, utils


def all_csv(request):
    # Get current season for PlayerStatSeason lookup
    current_season = datetime.datetime.now().year
    
    # # Get carded players by checking PlayerStatSeason
    # carded_player_ids = models.PlayerStatSeason.objects.filter(
    #     season=current_season,
    #     carded=True
    # ).values_list('player_id', flat=True)
    
    team_players = (
        models.Player.objects.filter(team__isnull=False)
        .order_by(
            "team",
            "position",
            "-level_order",
            "last_name",
            "first_name",
        )
        .values(*settings.CSV_COLUMNS)
    )
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="all-teams-%s.csv"' % (
        datetime.datetime.now().isoformat().split(".")[0]
    )
    writer = csv.DictWriter(response, fieldnames=settings.CSV_COLUMNS)
    writer.writeheader()
    for p in team_players:
        for k, v in p.items():
            if v == True:
                p[k] = "x"
            if v == False:
                p[k] = ""
        if p["defense"]:
            p["defense"] = ",".join(
                [f"{d.split('-')[0]}{d.split('-')[2]}" for d in p["defense"]]
            )
        else:
            p["defense"] = ""
        writer.writerow(p)
    return response


def team_csv(request, abbreviation):
    team = get_object_or_404(models.Team, abbreviation__icontains=abbreviation)
    team_players = (
        models.Player.objects.filter(team=team)
        .order_by(
            "position",
            "-level_order",
            "last_name",
            "first_name",
        )
        .values(*settings.CSV_COLUMNS)
    )

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="%s-%s.csv"' % (
        abbreviation,
        datetime.datetime.now().isoformat().split(".")[0],
    )
    writer = csv.DictWriter(response, fieldnames=settings.CSV_COLUMNS)
    writer.writeheader()
    for p in team_players:
        for k, v in p.items():
            if v == True:
                p[k] = "x"
            if v == False:
                p[k] = ""
        if p["defense"]:
            p["defense"] = ",".join(
                [f"{d.split('-')[0]}{d.split('-')[2]}" for d in p["defense"]]
            )
        else:
            p["defense"] = ""
        writer.writerow(p)
    return response
