import csv
import datetime
import itertools
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import render, get_object_or_404, redirect
from django.db.models import Count, Avg, Sum, Max, Min, Q, Prefetch, Case, When, IntegerField, OuterRef, Subquery
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.http import JsonResponse
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages

import ujson as json
from datetime import datetime

from ulmg import models, utils
from ulmg.cache_utils import (
    cache_key,
    get_cached_or_compute,
    get_all_cache_keys,
    delete_cache_key_for_admin,
    is_valkey_active,
)


def trade_block(request):
    context = utils.build_context(request)
    context['hitters'] = models.Player.objects.filter(team__isnull=False, is_trade_block=True).exclude(position="P").order_by('position')
    context['pitchers'] = models.Player.objects.filter(team__isnull=False, is_trade_block=True, position__icontains="P")

    return render(request, "trade_block.html", context)


def index(request):
    context = utils.build_context(request)
    season = utils.get_current_season()

    def _get_teams():
        from django.db.models import Count, Q
        return list(models.Team.objects.select_related('owner_obj').annotate(
            c_count=Count('player', filter=Q(player__position='C')),
            if_count=Count('player', filter=Q(player__position='IF')),
            of_count=Count('player', filter=Q(player__position='OF')),
            p_count=Count('player', filter=Q(player__position='P')),
            if_of_count=Count('player', filter=Q(player__position='IF-OF')),
            p_of_count=Count('player', filter=Q(player__position='OF-P')),
            p_if_count=Count('player', filter=Q(player__position='IF-P')),
            v_level_count=Count('player', filter=Q(player__level='V')),
            a_level_count=Count('player', filter=Q(player__level='A')),
            b_level_count=Count('player', filter=Q(player__level='B')),
            total_players=Count('player')
        ).order_by('division', 'abbreviation'))

    def _get_hitter_stats():
        base_stats = models.PlayerStatSeason.objects.filter(
            season=season,
            classification="1-mlb",
            player__team__isnull=True,
            is_career=False,
        )
        return list(base_stats.exclude(player__position="P").filter(hit_stats__pa__gte=1).select_related('player').order_by(
            "player__position", "-player__level_order", "player__last_name", "player__first_name"
        ))

    def _get_pitcher_stats():
        base_stats = models.PlayerStatSeason.objects.filter(
            season=season,
            classification="1-mlb",
            player__team__isnull=True,
            is_career=False,
        )
        return list(base_stats.filter(player__position__icontains="P").filter(pitch_stats__g__gte=1).select_related('player').order_by(
            "-player__level_order", "player__last_name", "player__first_name"
        ))

    context["teams"] = get_cached_or_compute(cache_key("index", "teams", season), _get_teams)
    context["hitters"] = get_cached_or_compute(cache_key("index", "hitters", season), _get_hitter_stats)
    context["pitchers"] = get_cached_or_compute(cache_key("index", "pitchers", season), _get_pitcher_stats)
    context["season"] = season

    return render(request, "index.html", context)


def player(request, playerid):
    context = utils.build_context(request)

    def _get_player_data():
        p = models.Player.objects.get(id=playerid)
        trades = models.TradeReceipt.objects.filter(players__id=playerid).select_related('trade', 'team').order_by("-trade__date")
        draft_picks = models.DraftPick.objects.filter(player__id=playerid).select_related('team').order_by("-year", "-season")
        transactions = []
        for trade in trades:
            transactions.append({
                'type': 'trade',
                'date': trade.trade.date if trade.trade else None,
                'year': trade.trade.date.year if trade.trade and trade.trade.date else None,
                'description': f"Traded to {trade.team.abbreviation}",
                'team': trade.team,
                'details': trade.trade.summary() if trade.trade else "Trade details not available"
            })
        for pick in draft_picks:
            transactions.append({
                'type': 'draft',
                'date': None,
                'year': int(pick.year) if pick.year else None,
                'description': f"Drafted by {pick.team.abbreviation}" if pick.team else "Drafted",
                'team': pick.team,
                'details': f"{pick.season.title()} {pick.draft_type.upper()} Draft - Round {pick.draft_round}, Pick {pick.pick_number}" if pick.draft_round and pick.pick_number else f"{pick.season.title()} {pick.draft_type.upper()} Draft"
            })
        transactions.sort(key=lambda x: (x['year'] or 0, x['type'] == 'draft'), reverse=True)
        player_stats = models.PlayerStatSeason.objects.filter(player_id=playerid, is_career=False).order_by('-season', 'classification')
        if p.position == "P":
            pitcher_stats = list(player_stats.filter(pitch_stats__isnull=False))
            hitter_stats = None
        else:
            hitter_stats = list(player_stats.filter(hit_stats__isnull=False))
            pitcher_stats = None
        return {
            "p": p,
            "transactions": transactions,
            "hitter_stats": hitter_stats,
            "pitcher_stats": pitcher_stats,
        }

    player_data = get_cached_or_compute(cache_key("player", playerid), _get_player_data)
    context["p"] = player_data["p"]
    context["transactions"] = player_data["transactions"]
    context["hitter_stats"] = player_data["hitter_stats"]
    context["pitcher_stats"] = player_data["pitcher_stats"]

    return render(request, "player_detail.html", context)


def team_detail(request, abbreviation):
    context = utils.build_context(request)
    team = get_object_or_404(models.Team, abbreviation__icontains=abbreviation)
    context["team"] = team

    if request.user.is_authenticated:
        owner = models.Owner.objects.get(user=request.user)
        if owner.team() == team:
            context["own_team"] = True
        else:
            context["own_team"] = False
    else:
        context["own_team"] = False

    if request.user.is_superuser:
        context["own_team"] = True

    season = utils.get_current_season()
    team_abbr = team.abbreviation.upper()

    def _get_team_roster_data():
        team_players = models.Player.objects.filter(team=team).select_related('team').prefetch_related(
            Prefetch(
                'playerstatseason_set',
                queryset=models.PlayerStatSeason.objects.filter(season=season, is_career=False).order_by('classification'),
                to_attr='current_season_stats'
            )
        )
        roster_35 = models.Player.objects.filter(team=team, is_ulmg_35man_roster=True).count()
        mlb_count = models.Player.objects.filter(
            team=team,
            is_ulmg_mlb_roster=True,
            is_ulmg_aaa_roster=False,
            is_ulmg_reserve=False
        ).count()
        level_dist = list(team_players.values("level_order").annotate(Count("level_order")).order_by("level_order"))
        hitters = list(team_players.exclude(position="P").order_by("position", "-level_order", "last_name", "first_name"))
        pitchers = list(team_players.filter(position__icontains="P").order_by("-level_order", "last_name", "first_name"))
        return {
            "35_roster_count": roster_35,
            "mlb_roster_count": mlb_count,
            "level_distribution": level_dist,
            "num_owned": len(hitters) + len(pitchers),
            "hitters": hitters,
            "pitchers": pitchers,
        }

    roster_data = get_cached_or_compute(cache_key("team", team_abbr, "roster", season), _get_team_roster_data)
    context["35_roster_count"] = roster_data["35_roster_count"]
    context["mlb_roster_count"] = roster_data["mlb_roster_count"]
    context["level_distribution"] = roster_data["level_distribution"]
    context["num_owned"] = roster_data["num_owned"]
    context["hitters"] = roster_data["hitters"]
    context["pitchers"] = roster_data["pitchers"]
    context["compact_roster"] = True
    return render(request, "team.html", context)


def team_other(request, abbreviation):
    context = utils.build_context(request)
    team = get_object_or_404(models.Team, abbreviation__icontains=abbreviation)
    context["team"] = team

    if request.user.is_authenticated:
        owner = models.Owner.objects.get(user=request.user)
        if owner.team() == team:
            context["own_team"] = True
        else:
            context["own_team"] = False
    else:
        context["own_team"] = False

    team_abbr = team.abbreviation.upper()

    def _get_team_other_data():
        team_players = models.Player.objects.filter(team=team)
        level_dist = list(team_players.order_by("level_order").values("level_order").annotate(Count("level_order")))
        trades = list(models.Trade.objects.filter(teams=team).order_by("-date"))
        picks = list(models.DraftPick.objects.filter(team=team).order_by("-year", "season", "draft_type", "draft_round", "pick_number"))
        return {
            "level_distribution": level_dist,
            "num_owned": team_players.count(),
            "mlb_roster_count": models.Player.objects.filter(
                team=team,
                is_ulmg_mlb_roster=True,
                is_ulmg_aaa_roster=False,
                is_ulmg_reserve=False
            ).count(),
            "trades": trades,
            "picks": picks,
        }

    other_data = get_cached_or_compute(cache_key("team", team_abbr, "other"), _get_team_other_data)
    context["level_distribution"] = other_data["level_distribution"]
    context["num_owned"] = other_data["num_owned"]
    context["mlb_roster_count"] = other_data["mlb_roster_count"]
    context["trades"] = other_data["trades"]
    context["picks"] = other_data["picks"]
    return render(request, "team_other.html", context)

def trades(request):
    context = utils.build_context(request)
    context["archived_trades"] = models.TradeSummary.objects.all()
    context["trades"] = models.Trade.objects.all().order_by("-date")
    return render(request, "trade_list.html", context)


@staff_member_required
@login_required
def cache_admin(request):
    """Admin page to view all cache keys and purge individual keys."""
    context = utils.build_context(request)
    context["valkey_active"] = is_valkey_active()
    context["cache_keys"] = get_all_cache_keys() if context["valkey_active"] else []

    if request.method == "POST" and request.POST.get("key"):
        key_to_delete = request.POST.get("key")
        if context["valkey_active"] and key_to_delete in context["cache_keys"]:
            if delete_cache_key_for_admin(key_to_delete):
                messages.success(request, f"Purged cache key: {key_to_delete}")
            else:
                messages.success(request, f"Key {key_to_delete} purged or already expired")
        return redirect("cache_admin")

    return render(request, "cache_admin.html", context)


def draft_list(request):
    """Simple draft index page listing all drafts from settings.DRAFTS."""
    context = utils.build_context(request)
    return render(request, "draft_list.html", context)


def draft_admin(request, year, season, draft_type):
    context = utils.build_context(request)
    context["picks"] = models.DraftPick.objects.filter(
        year=year, season=season, draft_type=draft_type
    )

    def format_player_for_autocomplete(p):
        """Format player data for autocomplete display, handling None values gracefully."""
        mlb_org = p.get('current_mlb_org')
        mlbam_id = p.get('mlbam_id')
        
        # Base format: "POS Name"
        display = f"{p.get('position')} {p.get('name')}"
        
        # Add team info if available
        if mlb_org:
            display += f" {mlb_org}"
        
        # Add MLB ID if available for additional context
        if mlbam_id:
            display += f" {mlbam_id}"
        
        # Always add the Django pk at the end for reliable lookup (hidden from user)
        display += f" | {p.get('id')}"
        
        return display

    if draft_type == "aa":
        context["players"] = json.dumps(
            [
                format_player_for_autocomplete(p)
                for p in models.Player.objects.filter(team__isnull=True, level="B").values('current_mlb_org', 'mlbam_id', 'id', 'position', 'name')
            ]
        )

    if draft_type == "open":
        players = []
        for p in models.Player.objects.filter(team__isnull=True).exclude(level="B").values('current_mlb_org', 'mlbam_id', 'id', 'position', 'name'):
            players.append(format_player_for_autocomplete(p))

        if season == "offseason":
            # 35-man roster is a form of protection for offseason drafts?
            current_season = settings.CURRENT_SEASON
            # Get players not on 35-man roster via PlayerStatSeason
            players_not_35man = models.Player.objects.filter(
                is_owned=True,
                level__in=["V","A"],
                team__isnull=False,
                is_ulmg_1h_c=False,
                is_ulmg_1h_p=False,
                is_ulmg_1h_pos=False,
                is_ulmg_reserve=False,
            ).exclude(
                playerstatseason__season=current_season,
                playerstatseason__is_ulmg35man_roster=True
            ).exclude(
                playerstatseason__season=current_season,
                playerstatseason__is_ulmg_mlb_roster=True
            ).values('current_mlb_org', 'mlbam_id', 'id', 'position', 'name')
            
            for p in players_not_35man:
                players.append(format_player_for_autocomplete(p))

        if season == "midseason":
            # have to have been previously protected.
            for p in models.Player.objects.filter(
                is_owned=True,
                level="V",
                team__isnull=False,
                is_ulmg_midseason_unprotected=True
            ).values('current_mlb_org', 'mlbam_id', 'id', 'position', 'name'):
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
    current_season = settings.CURRENT_SEASON
    
    # For midseason availability, get unowned players with MLB stats or owned level V players not on MLB roster
    unowned_with_mlb_stats = models.PlayerStatSeason.objects.filter(
        season=current_season,
        classification="1-mlb",
        player__team__isnull=True,
        hit_stats__pa__gte=1,
        is_career=False,
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
        player__position__icontains="P",
        is_career=False,
    ).select_related('player')
    
    for stat_season in unowned_pitchers_with_mlb_stats:
        context["pitchers"].append(stat_season.player)
    
    # # Add owned level V pitchers not on MLB roster
    # for player in owned_level_v_not_mlb.filter(position="P", is_ulmg_1h_p=False):
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
    current_season = settings.CURRENT_SEASON
    
    # Get owned players not on 35-man roster
    available_players = models.Player.objects.filter(
        is_owned=True, 
        level__in=["A", "V"]
    ).exclude(
        playerstatseason__season=current_season,
        playerstatseason__is_ulmg35man_roster=True
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
    Returns Player objects that use get_best_stat_season() method for stats display.
    """
    context = utils.build_context(request)
    
    # Start with Player objects directly
    query = models.Player.objects.all()
    
    # Handle name search
    if request.GET.get("name", None):
        name = request.GET["name"].strip()
        if name:
            query = query.filter(name__icontains=name)
            context["name"] = name
    
    # Split into hitters and pitchers for the template, order by player fields
    context["hitters"] = query.exclude(position="P").order_by("position", "-level_order", "last_name", "first_name")
    context["pitchers"] = query.filter(position__icontains="P").order_by("-level_order", "last_name", "first_name")
    
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
    # Exclude career rows from all search results
    stat_season_query = models.PlayerStatSeason.objects.select_related('player').filter(is_career=False)
    
    # Default season for filtering - use get_current_season() to get previous year's stats during preseason/offseason
    search_season = utils.get_current_season()
    
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
    
    stat_season_query = stat_season_query.order_by('player__position', '-player__level_order', 'player__last_name', 'player__first_name')

    # # Apply filtering and deduplication
    # # To avoid showing duplicate players (same player with multiple classifications),
    # # we'll use Python-based deduplication to get the best record per player
    
    # # Get all filtered records with priority scoring
    # from django.db.models import Case, When, IntegerField
    
    # # Create a priority score for each record
    # priority_annotation = Case(
    #     # Highest priority: Major league records with hitting stats
    #     When(
    #         classification='1-mlb',
    #         hit_stats__PA__gt=0,
    #         then=1
    #     ),
    #     # Second priority: Major league records with pitching stats  
    #     When(
    #         classification='1-mlb',
    #         pitch_stats__G__gt=0,
    #         then=2
    #     ),
    #     # Third priority: Minor league records with hitting stats
    #     When(
    #         classification='2-minors',
    #         hit_stats__PA__gt=0,
    #         then=3
    #     ),
    #     # Fourth priority: Minor league records with pitching stats
    #     When(
    #         classification='2-minors', 
    #         pitch_stats__G__gt=0,
    #         then=4
    #     ),
    #     # Fifth priority: Any major league record (even without stats)
    #     When(classification='1-mlb', then=5),
    #     # Lowest priority: Any other record
    #     default=6,
    #     output_field=IntegerField()
    # )
    
    # # Get all records with priority annotation, ordered by priority
    # all_records = stat_season_query.annotate(
    #     priority=priority_annotation
    # ).order_by('priority', '-id')
    
    # # Deduplicate in Python: keep only the best record per player
    # seen_players = set()
    # deduplicated_records = []
    
    # for record in all_records:
    #     if record.player_id not in seen_players:
    #         deduplicated_records.append(record)
    #         seen_players.add(record.player_id)
    
    # # Sort the deduplicated records for display
    # deduplicated_records.sort(key=lambda r: (
    #     r.player.position, 
    #     -r.player.level_order, 
    #     r.player.last_name, 
    #     r.player.first_name
    # ))

    context["hitters"] = [r for r in stat_season_query if r.player.position != "P"]
    context["pitchers"] = [r for r in stat_season_query if "P" in r.player.position]

    # # Split into hitters and pitchers
    # context["hitters"] = [r for r in deduplicated_records if r.player.position != "P"]
    # context["pitchers"] = [r for r in deduplicated_records if "P" in r.player.position]
    
    # Filters visible by default for advanced filtering
    context["show_filters_by_default"] = True
    
    return render(request, "search.html", context)


