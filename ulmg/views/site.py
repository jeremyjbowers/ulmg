import csv
import datetime
import itertools
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import render, get_object_or_404
from django.db.models import Count, Avg, Sum, Max, Min, Q
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.http import JsonResponse
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db.models import Q

import ujson as json
from datetime import datetime

from ulmg import models, utils


def trade_block(request):
    context = utils.build_context(request)
    context['hitters'] = models.Player.objects.filter(team__isnull=False, is_trade_block=True).exclude(position="P").order_by('position')
    context['pitchers'] = models.Player.objects.filter(team__isnull=False, is_trade_block=True, position__icontains="P")

    return render(request, "trade_block.html", context)


def best_available(request, year):
    context = utils.build_context(request)
    context["hitters"] = []
    context["pitchers"] = []
    all_players = []

    with open(f"data/{year}/best_available.json", "r") as readfile:
        all_players = [
            p
            for idx, p in enumerate(json.loads(readfile.read()))
            if int(p["rank"]) < 1001
        ]

    context["top"] = [p for p in sorted(all_players, key=lambda x: int(x["rank"]))][:15]

    position_players = [
        p
        for p in sorted(all_players, key=lambda x: (x["ulmg_position"], int(x["rank"])))
    ]
    for p in position_players:
        if "P" not in p["position"]:
            context["hitters"].append(p)
        else:
            context["pitchers"].append(p)

    return render(request, "best_available.html", context)


def venue_list(request):
    context = utils.build_context(request)
    context["venues"] = models.Venue.objects.all().order_by("-park_factor", "name")

    return render(request, "venue_list.html", context)


def current_calendar(request):
    context = utils.build_context(request)
    today = datetime.today()
    context["season"] = utils.get_ulmg_season(today)
    context["future"] = models.Occurrence.objects.filter(
        season=context["season"], date__gte=today
    ).order_by("date", "time")
    context["past"] = models.Occurrence.objects.filter(
        season=context["season"], date__lt=today
    ).order_by("-date", "-time")
    context["total"] = models.Occurrence.objects.filter(
        season=context["season"]
    ).count()

    return render(request, "calendar.html", context)


def calendar_by_season(request, year):
    context = utils.build_context(request)
    today = datetime.today()
    context["season"] = year
    context["future"] = models.Occurrence.objects.filter(
        season=context["season"], date__gte=today
    ).order_by("date")
    context["past"] = models.Occurrence.objects.filter(
        season=context["season"], date__lt=today
    ).order_by("-date")
    context["total"] = models.Occurrence.objects.filter(
        season=context["season"]
    ).count()

    return render(request, "calendar.html", context)


def prospect_ranking_list(request, year):
    context = utils.build_context(request)
    context["year"] = year
    context["top_100"] = models.ProspectRating.objects.filter(
        year=year, rank_type="top-100"
    ).order_by("avg")
    context["top_draft"] = models.ProspectRating.objects.filter(
        year=year, rank_type="top-draft"
    ).order_by("avg")
    team_score_dict = {a.abbreviation: 0 for a in models.Team.objects.all()}
    for ranking_type, max_points in [
        (context["top_100"], 300),
        (context["top_draft"], 100),
    ]:
        for r in ranking_type:
            if r.player:
                if r.player.team:
                    score = int(max_points / float(r.avg))
                    team_score_dict[r.player.team.abbreviation] += score

    context["team_scores"] = sorted(
        [{"team": k, "score": v} for k, v in team_score_dict.items()],
        key=lambda x: x["score"],
        reverse=True,
    )
    return render(request, "prospect_ranking_list.html", context)

def index(request):
    context = utils.build_context(request)
    context["teams"] = models.Team.objects.all()

    season = 2025

    # Get PlayerStatSeason objects for unowned 2025 MLB major league players
    base_stats = models.PlayerStatSeason.objects.select_related('player').filter(
        season=season,
        classification="1-majors",  # MLB major league only (excludes NPB, KBO, NCAA, minors)
        owned=False    # Unowned only
    )

    # Split into hitters and pitchers by position
    hitter_stats = base_stats.exclude(player__position="P").order_by(
        "player__position", "-player__level_order", "player__last_name", "player__first_name"
    )
    
    pitcher_stats = base_stats.filter(player__position__icontains="P").order_by(
        "-player__level_order", "player__last_name", "player__first_name"
    )

    context["hitters"] = hitter_stats
    context["pitchers"] = pitcher_stats

    # Leaderboards using PlayerStatSeason objects directly
    context['hitter_hr'] = hitter_stats.filter(
        hit_stats__hr__gte=5
    ).order_by('-hit_stats__hr')[:10]
    
    context['hitter_sb'] = hitter_stats.filter(
        hit_stats__sb__gte=5
    ).order_by('-hit_stats__sb')[:10]
    
    context['hitter_avg'] = hitter_stats.filter(
        hit_stats__plate_appearances__gte=50
    ).order_by('-hit_stats__avg')[:10]
    
    context['pitcher_innings'] = pitcher_stats.filter(
        pitch_stats__ip__gte=10
    ).order_by('-pitch_stats__ip')[:10]
    
    context['pitcher_starts'] = pitcher_stats.filter(
        pitch_stats__gs__gte=1
    ).order_by('-pitch_stats__gs')[:10]
    
    context['pitcher_era'] = pitcher_stats.filter(
        pitch_stats__ip__gte=20
    ).order_by('pitch_stats__era')[:10]

    return render(request, "index.html", context)


def player(request, playerid):
    context = utils.build_context(request)
    context["p"] = models.Player.objects.get(id=playerid)
    context["trades"] = models.TradeReceipt.objects.filter(
        players__id=playerid
    ).order_by("-trade__date")
    context["drafted"] = models.DraftPick.objects.filter(player__id=playerid)
    return render(request, "player_detail.html", context)


def team_detail(request, abbreviation):
    context = utils.build_context(request)
    context["team"] = get_object_or_404(
        models.Team, abbreviation__icontains=abbreviation
    )
    if request.user.is_authenticated:
        owner = models.Owner.objects.get(user=request.user)
        if owner.team() == context["team"]:
            context["own_team"] = True
        else:
            context["own_team"] = False
    else:
        context["own_team"] = False

    if request.user.is_superuser:
        context["own_team"] = True

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
    pitchers = team_stat_seasons.filter(player__position__icontains="P").order_by(
        "-player__level_order", "-player__is_carded", 
        "player__last_name", "player__first_name"
    )

    context["hitters"] = hitters
    context["pitchers"] = pitchers
    return render(request, "team.html", context)


def team_other(request, abbreviation):
    context = utils.build_context(request)
    team = get_object_or_404(models.Team, abbreviation__icontains=abbreviation)
    context["team"] = team

    if request.user.is_authenticated:
        owner = models.Owner.objects.get(user=request.user)
        if owner.team() == context["team"]:
            context["own_team"] = True
        else:
            context["own_team"] = False
    else:
        context["own_team"] = False

    team_players = models.Player.objects.filter(team=context["team"])
    context["level_distribution"] = (
        team_players.order_by("level_order")
        .values("level_order")
        .annotate(Count("level_order"))
    )
    context["num_owned"] = models.Player.objects.filter(team=team).count()
    context["trades"] = models.Trade.objects.filter(teams=team).order_by("-date")
    context["picks"] = models.DraftPick.objects.filter(team=team).order_by(
        "-year", "season", "draft_type", "draft_round", "pick_number"
    )
    return render(request, "team_other.html", context)

def trades(request):
    context = utils.build_context(request)
    context["archived_trades"] = models.TradeSummary.objects.all()
    context["trades"] = models.Trade.objects.all().order_by("-date")
    return render(request, "trade_list.html", context)


def draft_admin(request, year, season, draft_type):
    context = utils.build_context(request)
    context["picks"] = models.DraftPick.objects.filter(
        year=year, season=season, draft_type=draft_type
    )

    def format_player_for_autocomplete(p):
        """Format player data for autocomplete display, handling None values gracefully."""
        mlb_org = p.get('mlb_org')
        mlbam_id = p.get('mlbam_id')
        
        # Base format: "POS Name"
        display = f"{p['position']} {p['name']}"
        
        # Add team info if available
        if mlb_org:
            display += f" {mlb_org}"
        
        # Add MLB ID if available for additional context
        if mlbam_id:
            display += f" {mlbam_id}"
        
        # Always add the Django pk at the end for reliable lookup (hidden from user)
        display += f" | {p['id']}"
        
        return display

    if draft_type == "aa":
        context["players"] = json.dumps(
            [
                format_player_for_autocomplete(p)
                for p in models.Player.objects.filter(is_owned=False, level="B").values(
                    "id", "name", "position", 'mlbam_id', 'mlb_org'
                )
            ]
        )

    if draft_type == "open":
        players = []
        for p in models.Player.objects.filter(is_owned=False).values(
            "id", "name", "position", 'mlbam_id', 'mlb_org'
        ):
            players.append(format_player_for_autocomplete(p))

        if season == "offseason":
            # 35-man roster is a form of protection for offseason drafts?
            for p in models.Player.objects.filter(
                is_owned=True,
                level__in=["V","A"],
                team__isnull=False,
                is_mlb_roster=False,
                is_1h_c=False,
                is_1h_p=False,
                is_1h_pos=False,
                is_35man_roster=False,
                is_reserve=False,
            ).values("id", "name", "position", 'mlbam_id', 'mlb_org'):
                players.append(format_player_for_autocomplete(p))

        if season == "midseason":
            # have to have been previously protected.
            for p in models.Player.objects.filter(
                is_owned=True,
                level="V",
                team__isnull=False,
                is_mlb_roster=False,
                is_1h_c=False,
                is_1h_p=False,
                is_1h_pos=False,
                is_reserve=False,
            ).values("id", "name", "position", 'mlbam_id', 'mlb_org'):
                players.append(format_player_for_autocomplete(p))

        context["players"] = json.dumps(players)

    context["year"] = year
    context["season"] = season
    context["draft_type"] = draft_type

    return render(request, "draft_admin.html", context)


def draft_watch(request, year, season, draft_type):
    context = utils.build_context(request)
    context["made_picks"] = (
        models.DraftPick.objects.filter(
            Q(player_name__isnull=False) | Q(player__isnull=False) | Q(skipped=True)
        )
        .filter(year=year, season=season, draft_type=draft_type)
        .order_by("year", "-season", "draft_type", "-draft_round", "-pick_number")
    )
    context["upcoming_picks"] = models.DraftPick.objects.filter(
        year=year, season=season, draft_type=draft_type
    ).exclude(Q(player_name__isnull=False) | Q(player__isnull=False) | Q(skipped=True))
    context["year"] = year
    context["season"] = season
    context["draft_type"] = draft_type

    return render(request, "draft_watch.html", context)


def draft_recap(request, year, season, draft_type):
    context = utils.build_context(request)
    context["picks"] = models.DraftPick.objects.filter(
        year=year, season=season, draft_type=draft_type
    ).order_by("year", "-season", "draft_type", "draft_round", "pick_number")
    context["year"] = year
    context["season"] = season
    context["draft_type"] = draft_type

    return render(request, "draft_recap.html", context)


def player_available_midseason(request):
    context = utils.build_context(request)
    context["hitters"] = (
        models.Player.objects.filter(
            Q(team__isnull=True, stats__2025_majors_hit__plate_appearances__gte=1)
            | Q(
                level="V",
                is_owned=True,
                is_mlb_roster=False,
                is_1h_c=False,
                is_1h_pos=False,
                is_reserve=False,
            )
        )
        .exclude(position="P")
        .order_by("position", "-level_order", "last_name", "first_name")
    )

    context["pitchers"] = models.Player.objects.filter(
        Q(team__isnull=True, stats__2025_majors_pitch__ip__gte=1, position__icontains="P")
        | Q(
            level="V",
            position="P",
            is_owned=True,
            is_mlb_roster=False,
            is_1h_p=False,
            is_reserve=False,
        )
    ).order_by("-level_order", "last_name", "first_name")

    return render(request, "search.html", context)


def player_available_offseason(request):
    context = utils.build_context(request)
    context["hitters"] = (
        models.Player.objects.filter(
            is_owned=True, is_35man_roster=False, level__in=["A", "V"]
        )
        .exclude(position="P")
        .order_by("position", "-level_order", "last_name", "first_name")
    )

    context["pitchers"] = models.Player.objects.filter(
        is_owned=True, is_35man_roster=False, level__in=["A", "V"], position__icontains="P"
    ).order_by("-level_order", "last_name", "first_name")

    return render(request, "search.html", context)


def search_by_name(request):
    """
    Search for players by name only.
    Uses PlayerStatSeason objects for consistent performance with filter search.
    """
    context = utils.build_context(request)
    
    # Start with PlayerStatSeason for current season (2025) with player relationship
    current_season = 2025
    query = models.PlayerStatSeason.objects.filter(season=current_season).select_related('player')
    
    # Handle name search through player relationship
    if request.GET.get("name", None):
        name = request.GET["name"].strip()
        if name:
            query = query.filter(player__name__icontains=name)
            context["name"] = name
    
    # Split into hitters and pitchers for the template, order by player fields
    context["hitters"] = query.exclude(player__position="P").order_by("player__position", "-player__level_order", "player__last_name", "player__first_name")
    context["pitchers"] = query.filter(player__position__icontains="P").order_by("-player__level_order", "player__last_name", "player__first_name")
    
    return render(request, "search.html", context)


def filter_players(request):
    """
    Filter players by various criteria (level, position, ownership status, stats, etc.).
    Uses PlayerStatSeason queries with indexes for optimal performance.
    """
    def to_bool(b):
        if b and b.lower() in ["y", "yes", "t", "true", "on"]:
            return True
        return False

    context = utils.build_context(request)
    
    # Start with PlayerStatSeason for indexed filtering, then get players
    stat_season_query = models.PlayerStatSeason.objects.select_related('player')
    
    # Default season for filtering
    search_season = 2025
    
    # Handle season selection first (most selective filter)
    if request.GET.get("season", None):
        season = request.GET['season'].strip()
        if season:
            try:
                search_season = int(season)
                context['season'] = f"{search_season}"
            except ValueError:
                pass  # Invalid year, use default
    
    # Filter by season (uses index)
    stat_season_query = stat_season_query.filter(season=search_season)
    
    # Handle classification filter (uses classification index)
    if request.GET.get("classification", None):
        classification = request.GET["classification"].strip()
        if classification:
            stat_season_query = stat_season_query.filter(classification=classification)
            context['classification'] = classification
    
    # Handle ownership filters (uses indexed fields)
    if request.GET.get("owned", None):
        owned = request.GET["owned"].strip()
        if owned:
            stat_season_query = stat_season_query.filter(owned=to_bool(owned))
            context["owned"] = owned
    
    if request.GET.get("carded", None):
        carded = request.GET["carded"].strip()
        if carded:
            stat_season_query = stat_season_query.filter(carded=to_bool(carded))
            context["carded"] = carded
    
    # Handle level filter (uses level index)
    if request.GET.get("level", None):
        level = request.GET["level"].strip()
        if level:
            stat_season_query = stat_season_query.filter(player__level=level)
            context["level"] = level
    
    # Handle stat cutoffs using JSON field lookups
    if request.GET.get('pa_cutoff', None):
        pa_cutoff = request.GET['pa_cutoff'].strip()
        if pa_cutoff:
            try:
                pa_cutoff = int(pa_cutoff)
                stat_season_query = stat_season_query.filter(hit_stats__plate_appearances__gte=pa_cutoff)
                context['pa_cutoff'] = f"{pa_cutoff}"
            except ValueError:
                pass  # Invalid integer, skip filter

    if request.GET.get('ip_cutoff', None):
        ip_cutoff = request.GET['ip_cutoff'].strip()
        if ip_cutoff:
            try:
                ip_cutoff = int(ip_cutoff)
                stat_season_query = stat_season_query.filter(pitch_stats__ip__gte=ip_cutoff)
                context['ip_cutoff'] = f"{ip_cutoff}"
            except ValueError:
                pass  # Invalid integer, skip filter

    if request.GET.get('gs_cutoff', None):
        gs_cutoff = request.GET['gs_cutoff'].strip()
        if gs_cutoff:
            try:
                gs_cutoff = int(gs_cutoff)
                stat_season_query = stat_season_query.filter(pitch_stats__gs__gte=gs_cutoff)
                context['gs_cutoff'] = f"{gs_cutoff}"
            except ValueError:
                pass  # Invalid integer, skip filter
    
    # Handle position filter on the PlayerStatSeason query
    if request.GET.get("position", None):
        position = request.GET["position"].strip()
        if position:
            if position.lower() == "h":
                stat_season_query = stat_season_query.exclude(player__position="P")
            elif position.lower() == "p":
                stat_season_query = stat_season_query.filter(player__position__icontains="P")
            else:
                stat_season_query = stat_season_query.filter(player__position__icontains=position)
            context["position"] = position
    
    # Apply ordering and split into hitters and pitchers for the template
    # Order by player fields through the relationship
    stat_seasons = stat_season_query.order_by("player__position", "-player__level_order", "player__last_name", "player__first_name")
    context["hitters"] = stat_seasons.exclude(player__position="P")
    context["pitchers"] = stat_seasons.filter(player__position__icontains="P")
    
    return render(request, "search.html", context)


