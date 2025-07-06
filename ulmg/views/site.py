import csv
import datetime
import itertools
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import render, get_object_or_404
from django.db.models import Count, Avg, Sum, Max, Min, Q, Prefetch, Case, When, IntegerField, OuterRef, Subquery
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.http import JsonResponse
from django.conf import settings
from django.contrib.auth.decorators import login_required

import ujson as json
from datetime import datetime

from ulmg import models, utils


def trade_block(request):
    context = utils.build_context(request)
    context['hitters'] = models.Player.objects.filter(team__isnull=False, is_trade_block=True).exclude(position="P").order_by('position')
    context['pitchers'] = models.Player.objects.filter(team__isnull=False, is_trade_block=True, position__icontains="P")

    return render(request, "trade_block.html", context)


def index(request):
    context = utils.build_context(request)
    context["teams"] = models.Team.objects.all()

    season = 2025

    # Get PlayerStatSeason objects for unowned 2025 MLB major league players WITH ACTUAL STATS
    # READ-HEAVY OPTIMIZATION: Use select_related to preload player data and avoid N+1 queries
    base_stats = models.PlayerStatSeason.objects.filter(
        season=season,
        classification="1-mlb",  # MLB major league only (excludes NPB, KBO, NCAA, minors)
        player__team__isnull=True    # Unowned only - uses partial index idx_unowned_mlb
    )

    # Split into hitters and pitchers by position
    # NOTE: Can also use new QuerySet methods: base_stats.with_hitting_stats() or base_stats.with_pitching_stats()
    hitter_stats = base_stats.exclude(player__position="P").filter(hit_stats__pa__gte=1).order_by(
        "player__position", "-player__level_order", "player__last_name", "player__first_name"
    )
    
    pitcher_stats = base_stats.filter(player__position__icontains="P").filter(pitch_stats__g__gte=1).order_by(
        "-player__level_order", "player__last_name", "player__first_name"
    )

    context["hitters"] = hitter_stats
    context["pitchers"] = pitcher_stats

    return render(request, "index.html", context)


def player(request, playerid):
    context = utils.build_context(request)
    context["p"] = models.Player.objects.get(id=playerid)
    
    # Get transaction history - trades and drafts
    trades = models.TradeReceipt.objects.filter(
        players__id=playerid
    ).select_related('trade', 'team').order_by("-trade__date")
    
    draft_picks = models.DraftPick.objects.filter(
        player__id=playerid
    ).select_related('team').order_by("-year", "-season")
    
    # Combine transactions into a single chronological list
    transactions = []
    
    # Add trades
    for trade in trades:
        transactions.append({
            'type': 'trade',
            'date': trade.trade.date if trade.trade else None,
            'year': trade.trade.date.year if trade.trade and trade.trade.date else None,
            'description': f"Traded to {trade.team.abbreviation}",
            'team': trade.team,
            'details': trade.trade.summary() if trade.trade else "Trade details not available"
        })
    
    # Add drafts
    for pick in draft_picks:
        transactions.append({
            'type': 'draft',
            'date': None,  # Draft picks don't have specific dates
            'year': int(pick.year) if pick.year else None,
            'description': f"Drafted by {pick.team.abbreviation}" if pick.team else "Drafted",
            'team': pick.team,
            'details': f"{pick.season.title()} {pick.draft_type.upper()} Draft - Round {pick.draft_round}, Pick {pick.pick_number}" if pick.draft_round and pick.pick_number else f"{pick.season.title()} {pick.draft_type.upper()} Draft"
        })
    
    # Sort by year (most recent first), then by type (trades before drafts for same year)
    transactions.sort(key=lambda x: (x['year'] or 0, x['type'] == 'draft'), reverse=True)
    context["transactions"] = transactions
    
    # Get all PlayerStatSeason records for this player, sorted by year desc, then classification
    player_stats = models.PlayerStatSeason.objects.filter(
        player_id=playerid
    ).order_by('-season', 'classification')
    
    # Split into hitters and pitchers based on player position
    player = context["p"]
    if player.position == "P":
        # Pitcher - only show pitching stats
        context["pitcher_stats"] = player_stats.filter(pitch_stats__isnull=False)
        context["hitter_stats"] = None
    else:
        # Hitter - only show hitting stats  
        context["hitter_stats"] = player_stats.filter(hit_stats__isnull=False)
        context["pitcher_stats"] = None
    
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

    # Get current season for PlayerStatSeason queries
    current_season = datetime.now().year

    # Get team players with current season data efficiently
    # This gets all players on the team, whether they have current season data or not
    team_players = models.Player.objects.filter(
        team=context["team"]
    ).select_related('team').prefetch_related(
        # Prefetch current season PlayerStatSeason data (ordered by classification)
        Prefetch(
            'playerstatseason_set',
            queryset=models.PlayerStatSeason.objects.filter(season=current_season).order_by('classification'),
            to_attr='current_season_stats'
        )
    )
    
    # Count roster statuses using optimized PlayerStatSeason queries
    # Use direct queries for better performance
    context["35_roster_count"] = models.PlayerStatSeason.objects.filter(
        player__team=context["team"], 
        season=current_season,
        is_35man_roster=True
    ).count()
    
    context["mlb_roster_count"] = models.PlayerStatSeason.objects.filter(
        player__team=context["team"],
        season=current_season,
        is_mlb_roster=True, 
        is_aaa_roster=False,
        player__is_reserve=False
    ).count()
    
    # Use optimized aggregation for level distribution
    context["level_distribution"] = (
        team_players.values("level_order")
        .annotate(Count("level_order"))
        .order_by("level_order")
    )
    context["num_owned"] = team_players.count()

    # Query for players directly with optimized ordering
    # Split into hitters and pitchers, then sort as desired
    hitters = team_players.exclude(position="P").order_by(
        "position", "-level_order", "last_name", "first_name"
    )
    
    pitchers = team_players.filter(position__icontains="P").order_by(
        "-level_order", "last_name", "first_name"
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
            current_season = datetime.now().year
            # Get players not on 35-man roster via PlayerStatSeason
            players_not_35man = models.Player.objects.filter(
                is_owned=True,
                level__in=["V","A"],
                team__isnull=False,
                is_1h_c=False,
                is_1h_p=False,
                is_1h_pos=False,
                is_reserve=False,
            ).exclude(
                playerstatseason__season=current_season,
                playerstatseason__is_35man_roster=True
            ).exclude(
                playerstatseason__season=current_season,
                playerstatseason__is_mlb_roster=True
            )
            
            for p in players_not_35man.values("id", "name", "position", 'mlbam_id'):
                # Get mlb_org from current season PlayerStatSeason if available
                player_obj = models.Player.objects.get(id=p['id'])
                current_status = player_obj.current_season_status()
                p['mlb_org'] = current_status.mlb_org if current_status else None
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
    current_season = 2025
    
    # For midseason availability, get unowned players with MLB stats or owned level V players not on MLB roster
    unowned_with_mlb_stats = models.PlayerStatSeason.objects.filter(
        season=current_season,
        classification="1-mlb",
        player__team__isnull=True,
        hit_stats__pa__gte=1
    ).select_related('player')
    
    # Combine queries for hitters
    context["hitters"] = []
    
    # Add unowned hitters with MLB stats
    for stat_season in unowned_with_mlb_stats.exclude(player__position="P"):
        context["hitters"].append(stat_season.player)
    
    # # Add owned level V hitters not on MLB roster
    # for player in owned_level_v_not_mlb.exclude(position="P"):
    #     context["hitters"].append(player)
    
    # Sort hitters
    context["hitters"] = sorted(
        set(context["hitters"]), 
        key=lambda p: (p.position, -p.level_order, p.last_name, p.first_name)
    )

    # Similar for pitchers
    context["pitchers"] = []
    
    # Add unowned pitchers with MLB stats
    unowned_pitchers_with_mlb_stats = models.PlayerStatSeason.objects.filter(
        season=current_season,
        classification="1-mlb",
        player__team__isnull=True,
        pitch_stats__ip__gte=1,
        player__position__icontains="P"
    ).select_related('player')
    
    for stat_season in unowned_pitchers_with_mlb_stats:
        context["pitchers"].append(stat_season.player)
    
    # # Add owned level V pitchers not on MLB roster
    # for player in owned_level_v_not_mlb.filter(position="P", is_1h_p=False):
    #     context["pitchers"].append(player)
    
    # Sort pitchers
    context["pitchers"] = sorted(
        set(context["pitchers"]), 
        key=lambda p: (-p.level_order, p.last_name, p.first_name)
    )

    # Filters hidden by default for midseason available players
    context["show_filters_by_default"] = False

    return render(request, "search.html", context)


def player_available_offseason(request):
    context = utils.build_context(request)
    current_season = datetime.now().year
    
    # Get owned players not on 35-man roster
    available_players = models.Player.objects.filter(
        is_owned=True, 
        level__in=["A", "V"]
    ).exclude(
        playerstatseason__season=current_season,
        playerstatseason__is_35man_roster=True
    )
    
    context["hitters"] = available_players.exclude(position="P").order_by(
        "position", "-level_order", "last_name", "first_name"
    )

    context["pitchers"] = available_players.filter(position__icontains="P").order_by(
        "-level_order", "last_name", "first_name"
    )

    # Filters hidden by default for offseason available players
    context["show_filters_by_default"] = False

    return render(request, "search.html", context)


def search_by_name(request):
    """
    Search for players by name only.
    Uses PlayerStatSeason objects for consistent performance with filter search.
    """
    context = utils.build_context(request)
    
    # Start with PlayerStatSeason for current season (2025) with optimized relationships
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
    
    # Filters hidden by default for simple name search
    context["show_filters_by_default"] = False
    
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
    
    # Start with PlayerStatSeason for indexed filtering with optimized select_related
    # Include player in select_related to avoid N+1 queries
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
    
    # Filter by season first (uses index and is most selective)
    stat_season_query = stat_season_query.filter(season=search_season)
    
    # Handle classification filter early (uses classification index)
    if request.GET.get("classification", None):
        classification = request.GET["classification"].strip()
        if classification:
            stat_season_query = stat_season_query.filter(classification=classification)
            context['classification'] = classification
    
    # Handle ownership filters early (uses indexed fields)
    if request.GET.get("owned", None):
        owned = request.GET["owned"].strip()
        if owned:
            stat_season_query = stat_season_query.exclude(player__team__isnull=to_bool(owned))
            context["owned"] = owned
    
    if request.GET.get("carded", None):
        carded = request.GET["carded"].strip()
        if carded:
            stat_season_query = stat_season_query.filter(player__carded_seasons__contains=[int(carded)])
            context["carded"] = carded
    
    # Handle level filter (uses level index)
    if request.GET.get("level", None):
        level = request.GET["level"].strip()
        if level:
            stat_season_query = stat_season_query.filter(player__level=level)
            context["level"] = level
    
    # Handle stat cutoffs using JSON field lookups (apply after other filters for efficiency)
    if request.GET.get('pa_cutoff', None):
        pa_cutoff = request.GET['pa_cutoff'].strip()
        if pa_cutoff:
            try:
                pa_cutoff = int(pa_cutoff)
                stat_season_query = stat_season_query.filter(hit_stats__pa__gte=pa_cutoff)
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
    
    # Handle position filter on the PlayerStatSeason query (apply late for best performance)
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
    
    # Apply filtering and deduplication
    # To avoid showing duplicate players (same player with multiple classifications),
    # we'll use Python-based deduplication to get the best record per player
    
    # Get all filtered records with priority scoring
    from django.db.models import Case, When, IntegerField
    
    # Create a priority score for each record
    priority_annotation = Case(
        # Highest priority: Major league records with hitting stats
        When(
            classification='1-mlb',
            hit_stats__PA__gt=0,
            then=1
        ),
        # Second priority: Major league records with pitching stats  
        When(
            classification='1-mlb',
            pitch_stats__G__gt=0,
            then=2
        ),
        # Third priority: Minor league records with hitting stats
        When(
            classification='2-minors',
            hit_stats__PA__gt=0,
            then=3
        ),
        # Fourth priority: Minor league records with pitching stats
        When(
            classification='2-minors', 
            pitch_stats__G__gt=0,
            then=4
        ),
        # Fifth priority: Any major league record (even without stats)
        When(classification='1-mlb', then=5),
        # Lowest priority: Any other record
        default=6,
        output_field=IntegerField()
    )
    
    # Get all records with priority annotation, ordered by priority
    all_records = stat_season_query.annotate(
        priority=priority_annotation
    ).order_by('priority', '-id')
    
    # Deduplicate in Python: keep only the best record per player
    seen_players = set()
    deduplicated_records = []
    
    for record in all_records:
        if record.player_id not in seen_players:
            deduplicated_records.append(record)
            seen_players.add(record.player_id)
    
    # Sort the deduplicated records for display
    deduplicated_records.sort(key=lambda r: (
        r.player.position, 
        -r.player.level_order, 
        r.player.last_name, 
        r.player.first_name
    ))
    
    # Split into hitters and pitchers
    context["hitters"] = [r for r in deduplicated_records if r.player.position != "P"]
    context["pitchers"] = [r for r in deduplicated_records if "P" in r.player.position]
    
    # Filters visible by default for advanced filtering
    context["show_filters_by_default"] = True
    
    return render(request, "search.html", context)


