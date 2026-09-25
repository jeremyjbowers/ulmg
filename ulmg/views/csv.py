# ABOUTME: CSV download views for roster and trade exports.
# ABOUTME: Builds attachment responses for teams and full trade history.
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


TRADE_CSV_FIELDNAMES = [
    "trade_id",
    "date",
    "season",
    "team_1",
    "team_1_receives_players",
    "team_1_receives_picks",
    "team_2",
    "team_2_receives_players",
    "team_2_receives_picks",
]


def _format_trade_players(players):
    return ", ".join(
        f"{p.position} {p.name}".strip() for p in players
    )


def _format_trade_pick(pick):
    team_abbr = (
        pick.original_team.abbreviation if pick.original_team else ""
    )
    season_label = (pick.season or "").title()
    draft_type = (pick.draft_type or "").upper()
    draft_round = pick.draft_round if pick.draft_round is not None else ""
    parts = [team_abbr, str(pick.year), season_label, f"{draft_type}{draft_round}"]
    label = " ".join(part for part in parts if part).strip()
    if pick.player:
        label = f"{label} ({pick.player.position} {pick.player.name})"
    return label


def _format_trade_picks(picks):
    return ", ".join(_format_trade_pick(pick) for pick in picks)


def trades_csv(request):
    """CSV export of all trades for pattern / return analysis."""
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="trades-%s.csv"' % (
        datetime.datetime.now().isoformat().split(".")[0]
    )
    writer = csv.DictWriter(response, fieldnames=TRADE_CSV_FIELDNAMES)
    writer.writeheader()

    trades = models.Trade.objects.order_by("-date", "-id")
    for trade in trades:
        receipts = list(
            trade.reciepts()
            .select_related("team")
            .prefetch_related("players", "picks__original_team", "picks__player")
        )
        if len(receipts) < 2:
            continue

        t1, t2 = receipts[0], receipts[1]
        writer.writerow(
            {
                "trade_id": trade.id,
                "date": trade.date.isoformat() if trade.date else "",
                "season": trade.season if trade.season is not None else "",
                "team_1": t1.team.abbreviation if t1.team else "",
                "team_1_receives_players": _format_trade_players(t1.players.all()),
                "team_1_receives_picks": _format_trade_picks(t1.picks.all()),
                "team_2": t2.team.abbreviation if t2.team else "",
                "team_2_receives_players": _format_trade_players(t2.players.all()),
                "team_2_receives_picks": _format_trade_picks(t2.picks.all()),
            }
        )

    return response


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
        .values("id", *settings.CSV_COLUMNS)
    )
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="all-teams-%s.csv"' % (
        datetime.datetime.now().isoformat().split(".")[0]
    )
    # Create fieldnames list with mlb_id instead of mlbam_id for CSV headers
    csv_fieldnames = [f.replace("mlbam_id", "mlb_id") for f in settings.CSV_COLUMNS]
    writer = csv.DictWriter(response, fieldnames=csv_fieldnames)
    writer.writeheader()
    for p_dict in team_players:
        # Get the actual Player object to access get_best_stat_season
        player = models.Player.objects.get(id=p_dict["id"])
        best_stat_season = player.get_best_stat_season()
        
        # Use defense from PlayerStatSeason only, no fallback to Player
        if best_stat_season and best_stat_season.defense:
            defense_list = best_stat_season.defense
        else:
            defense_list = []
        
        for k, v in p_dict.items():
            if v == True:
                p_dict[k] = "x"
            if v == False:
                p_dict[k] = ""
        
        if defense_list:
            p_dict["defense"] = ",".join(
                [f"{d.split('-')[0]}{d.split('-')[2]}" for d in defense_list]
            )
        else:
            p_dict["defense"] = ""
        # Remove 'id' from dict before writing to CSV (it's only needed for Player lookup)
        p_dict.pop("id", None)
        # Rename mlbam_id to mlb_id for CSV output
        if "mlbam_id" in p_dict:
            p_dict["mlb_id"] = p_dict.pop("mlbam_id")
        writer.writerow(p_dict)
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
        .values("id", *settings.CSV_COLUMNS)
    )

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="%s-%s.csv"' % (
        abbreviation,
        datetime.datetime.now().isoformat().split(".")[0],
    )
    # Create fieldnames list with mlb_id instead of mlbam_id for CSV headers
    csv_fieldnames = [f.replace("mlbam_id", "mlb_id") for f in settings.CSV_COLUMNS]
    writer = csv.DictWriter(response, fieldnames=csv_fieldnames)
    writer.writeheader()
    for p_dict in team_players:
        # Get the actual Player object to access get_best_stat_season
        player = models.Player.objects.get(id=p_dict["id"])
        best_stat_season = player.get_best_stat_season()
        
        # Use defense from PlayerStatSeason only, no fallback to Player
        if best_stat_season and best_stat_season.defense:
            defense_list = best_stat_season.defense
        else:
            defense_list = []
        
        for k, v in p_dict.items():
            if v == True:
                p_dict[k] = "x"
            if v == False:
                p_dict[k] = ""
        
        if defense_list:
            p_dict["defense"] = ",".join(
                [f"{d.split('-')[0]}{d.split('-')[2]}" for d in defense_list]
            )
        else:
            p_dict["defense"] = ""
        # Remove 'id' from dict before writing to CSV (it's only needed for Player lookup)
        p_dict.pop("id", None)
        # Rename mlbam_id to mlb_id for CSV output
        if "mlbam_id" in p_dict:
            p_dict["mlb_id"] = p_dict.pop("mlbam_id")
        writer.writerow(p_dict)
    return response
