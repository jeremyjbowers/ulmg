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

import ujson as json
from datetime import datetime

from ulmg import models, utils


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

    season = datetime.today().year

    if datetime.today().month < 4:
        season = datetime.today().year - 1

    hitter_dict = {
        "team__isnull": True,
        f"stats__{season}_majors__plate_appearances__gte": 1,
    }

    pitcher_dict = {
        "team__isnull": True,
        f"stats__{season}_majors__g__gte": 1,
        "position__icontains": "P",
    }

    context["hitters"] = (
        models.Player.objects.filter(**hitter_dict)
        .exclude(position="P")
        .order_by("position", "-level_order", "last_name", "first_name")
    )

    context["pitchers"] = models.Player.objects.filter(**pitcher_dict).order_by(
        "-level_order", "last_name", "first_name"
    )

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

    team_players = models.Player.objects.filter(team=context["team"])
    hitters = team_players.exclude(position="P").order_by(
        "position", "-level_order", "-is_carded", "last_name", "first_name"
    )
    pitchers = team_players.filter(position__icontains="P").order_by(
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
    context["trades"] = models.TradeReceipt.objects.filter(
        team=team, trade__isnull=False
    ).order_by("-trade__date")
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

    if draft_type == "aa":
        context["players"] = json.dumps(
            [
                "%(name)s (%(position)s)" % p
                for p in models.Player.objects.filter(is_owned=False, level="B").values(
                    "name", "position"
                )
            ]
        )

    if draft_type == "open":
        players = []
        for p in models.Player.objects.filter(is_owned=False).values(
            "name", "position"
        ):
            players.append("%(name)s (%(position)s)" % p)

        if season == "offseason":
            # 35-man roster is a form of protection for offseason drafts?
            for p in models.Player.objects.filter(
                is_owned=True,
                level="V",
                team__isnull=False,
                is_mlb_roster=False,
                is_1h_c=False,
                is_1h_p=False,
                is_1h_pos=False,
                is_35man_roster=False,
                is_reserve=False,
            ).values("name", "position"):
                players.append("%(name)s (%(position)s)" % p)

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
            ).values("name", "position"):
                players.append("%(name)s (%(position)s)" % p)

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
            Q(team__isnull=True, stats__2022_majors__plate_appearances__gte=1)
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
        Q(team__isnull=True, stats__2022_majors__ip__gte=1, position__icontains="P")
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


def search(request):
    def to_bool(b):
        if b.lower() in ["y", "yes", "t", "true", "on"]:
            return True
        return False

    context = utils.build_context(request)

    query = models.Player.objects.all()

    if request.GET.get("protected", None):
        protected = request.GET["protected"]
        if protected.lower() != "":
            if to_bool(protected) == False:
                query = query.filter(
                    Q(is_1h_c=False),
                    Q(is_1h_p=False),
                    Q(is_1h_pos=False),
                    Q(is_35man_roster=False),
                    Q(is_reserve=False),
                ).exclude(level="B")
            else:
                query = query.filter(
                    Q(is_1h_c=True)
                    | Q(is_1h_p=True)
                    | Q(is_1h_pos=True)
                    | Q(is_35man_roster=True)
                    | Q(is_reserve=True)
                )

            context["protected"] = protected

    if request.GET.get("midseason", None):
        midseason = request.GET["midseason"]
        if midseason.lower() != "":
            if to_bool(midseason) == True:
                query = query.filter(
                    Q(stats__2022_majors__plate_appearances__gte=5)
                    | Q(stats__2022_majors__g__gte=2)
                )
            context["midseason"] = midseason

    if request.GET.get("name", None):
        name = request.GET["name"]
        query = query.filter(name__icontains=name)
        context["name"] = name

    if request.GET.get("position", None):
        position = request.GET["position"]
        if position.lower() not in ["", "h"]:
            query = query.filter(position__icontains=position)
            context["position"] = position
        elif position.lower() == "h":
            query = query.exclude(position="P")
            context["position"] = position

    if request.GET.get('pa_cutoff', None):
        pa_cutoff = int(request.GET['pa_cutoff'])
        if pa_cutoff:
            query = query.filter(stats__2023_majors__plate_appearances__gte=pa_cutoff)
            context['pa_cutoff'] = f"{pa_cutoff}"

    if request.GET.get('ip_cutoff', None):
        ip_cutoff = int(request.GET['ip_cutoff'])
        if ip_cutoff:
            query = query.filter(stats__2023_majors__ip__gte=ip_cutoff)
            context['ip_cutoff'] = f"{ip_cutoff}"

    if request.GET.get('gs_cutoff', None):
        gs_cutoff = int(request.GET['gs_cutoff'])
        if gs_cutoff:
            query = query.filter(stats__2023_majors__gs__gte=gs_cutoff)
            context['gs_cutoff'] = f"{gs_cutoff}"

    if request.GET.get("level", None):
        level = request.GET["level"]
        if level.lower() != "":
            query = query.filter(level=level)
            context["level"] = level

    if request.GET.get("reliever", None):
        reliever = request.GET["reliever"]
        if reliever.lower() != "":
            query = query.filter(is_relief_eligible=to_bool(reliever))
            if to_bool(reliever) == False:
                query = query.filter(starts__isnull=False).exclude(starts=0)
            context["reliever"] = reliever

    if request.GET.get("prospect", None):
        prospect = request.GET["prospect"]
        if prospect.lower() != "":
            query = query.filter(is_prospect=to_bool(prospect))
            context["prospect"] = prospect

    if request.GET.get("owned", None):
        owned = request.GET["owned"]
        if owned.lower() != "":
            query = query.filter(is_owned=to_bool(owned))
            context["owned"] = owned

    if request.GET.get("carded", None):
        carded = request.GET["carded"]
        if carded.lower() != "":
            query = query.filter(is_carded=to_bool(carded))
            context["carded"] = carded

    if request.GET.get("amateur", None):
        amateur = request.GET["amateur"]
        if amateur.lower() != "":
            query = query.filter(is_amateur=to_bool(amateur))
            context["amateur"] = amateur

    query = query.order_by("level", "last_name")

    if request.GET.get("csv", None):
        c = request.GET["csv"]
        if c.lower() in ["y", "yes", "t", "true"]:
            query = query.values(*settings.CSV_COLUMNS)
            response = HttpResponse(content_type="text/csv")
            response["Content-Disposition"] = 'attachment; filename="search-%s.csv"' % (
                datetime.datetime.now().isoformat().split(".")[0]
            )
            writer = csv.DictWriter(response, fieldnames=settings.CSV_COLUMNS)
            writer.writeheader()
            for p in query:
                writer.writerow(p)
            return response

    query = query.order_by("position", "-level_order", "last_name")

    context["hitters"] = query.exclude(position="P")
    context["pitchers"] = query.filter(position__icontains="P")
    return render(request, "search.html", context)
