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

@csrf_exempt
def player_action(request, playerid, action):
    """
    # PROTECTION
    is_reserve = models.BooleanField(default=False)
    is_1h_p = models.BooleanField(default=False)
    is_1h_c = models.BooleanField(default=False)
    is_1h_pos = models.BooleanField(default=False)
    """

    if action == "to_35":
        p = get_object_or_404(models.Player, id=playerid)
        p.is_reserve = False
        p.is_1h_c = False
        p.is_1h_p = False
        p.is_1h_pos = False
        p.is_35man_roster = True
        p.save()

    if action == "unprotect":
        p = get_object_or_404(models.Player, id=playerid)
        p.is_reserve = False
        p.is_1h_c = False
        p.is_1h_p = False
        p.is_1h_pos = False
        p.is_35man_roster = False
        p.save()

    if action == "is_reserve":
        p = get_object_or_404(models.Player, id=playerid)
        old = models.Player.objects.filter(team=p.team, is_reserve=True).update(is_reserve=False)
        p.is_reserve = True
        p.save()


    if action == "is_1h_p":
        p = get_object_or_404(models.Player, id=playerid)
        old = models.Player.objects.filter(team=p.team, is_1h_p=True).update(is_1h_p=False)
        p.is_1h_p = True
        p.save()

    if action == "is_1h_c":
        p = get_object_or_404(models.Player, id=playerid)
        old = models.Player.objects.filter(team=p.team, is_1h_c=True).update(is_1h_c=False)
        p.is_1h_c = True
        p.save()

    if action == "is_1h_pos":
        p = get_object_or_404(models.Player, id=playerid)
        old = models.Player.objects.filter(team=p.team, is_1h_pos=True).update(is_1h_pos=False)
        p.is_1h_pos = True
        p.save()

    if action == "to_mlb":
        p = get_object_or_404(models.Player, id=playerid)
        p.is_mlb_roster = True
        p.is_aaa_roster = False
        p.save()

    if action == "to_aaa":
        p = get_object_or_404(models.Player, id=playerid)
        p.is_mlb_roster = False
        p.is_aaa_roster = True
        p.save()

    if action == "off_roster":
        p = get_object_or_404(models.Player, id=playerid)
        p.is_mlb_roster = False
        p.is_aaa_roster = False
        p.save()

    if action == "drop":
        p = get_object_or_404(models.Player, id=playerid)
        p.is_mlb_roster = False
        p.is_aaa_roster = False
        p.team = None
        p.is_owned = False
        p.is_reserve = False
        p.is_1h_c = False
        p.is_1h_p = False
        p.is_1h_pos = False
        p.save()

    return HttpResponse("ok")

def index(request):
    context = utils.build_context(request)
    context['rand_hit'] = models.Player.objects.filter(position__in=["IF", "OF", "IF/OF", "C"], is_owned=False, stats__isnull=False).order_by('?')[0:10]
    context['rand_pitch'] = models.Player.objects.filter(is_owned=False, position="P", stats__isnull=False).order_by('?')[0:10]
    context['carded_positions'] = models.Player.objects.filter(is_carded=True).order_by('position').values('position').annotate(Count('position'))
    context['uncarded_positions'] = models.Player.objects.filter(is_carded=False).order_by('position').values('position').annotate(Count('position'))

    return render(request, 'index.html', context)

def player(request, playerid):
    context = utils.build_context(request)
    context['player'] = models.Player.objects.get(id=playerid)

    return render(request, 'player_detail.html', context)    

def roster_team_detail(request, abbreviation):
    context = utils.build_context(request)
    context['team'] = get_object_or_404(models.Team, abbreviation__icontains=abbreviation)
    team_players = models.Player.objects.filter(team=context['team'])
    context['unrostered'] = team_players.filter(is_mlb_roster=False, is_aaa_roster=False, is_carded=True, is_1h_c=False, is_1h_p=False, is_1h_pos=False, is_reserve=False).order_by('position', '-level_order', 'last_name')
    context['mlb_roster'] = team_players.filter(is_mlb_roster=True, is_aaa_roster=False, is_1h_c=False, is_1h_p=False, is_1h_pos=False, is_reserve=False).order_by('position', '-level_order', 'last_name')
    context['cuttable_b'] = team_players.filter(level="B", is_mlb_roster=False, is_aaa_roster=False).order_by('position', 'last_name')
    context['uncarded_vets'] = team_players.filter(is_mlb_roster=False, is_aaa_roster=False, is_carded=False, is_1h_c=False, is_1h_p=False, is_1h_pos=False, is_reserve=False, level__in=["A", "V"]).order_by('position', '-level_order', 'last_name')
    context['num_mlb'] = context['mlb_roster'].count()
    context['protected_veterans'] = team_players.filter(Q(is_1h_c=True)|Q(is_1h_p=True)|Q(is_1h_pos=True)|Q(is_reserve=True)).order_by('position', '-level_order', 'last_name')
    context['aaa_roster'] = team_players.filter(is_aaa_roster=True, is_1h_c=False, is_1h_p=False, is_1h_pos=False, is_reserve=False).order_by('position', '-level_order', 'last_name')
    context['num_owned'] = team_players.count()
    team_players = models.Player.objects.filter(team=context['team'])
    return render(request, 'team_roster.html', context)

def protect_team_detail(request, abbreviation):
    context = utils.build_context(request)
    context['team'] = get_object_or_404(models.Team, abbreviation__icontains=abbreviation)
    team_players = models.Player.objects.filter(team=context['team'])
    context['on_35_man'] = team_players.filter(is_35man_roster=True).order_by('position', '-level_order', 'last_name')
    context['unprotected'] = team_players.filter(level__in=['V'], is_1h_c=False, is_1h_p=False, is_1h_pos=False, is_35man_roster=False, is_reserve=False).order_by('position', '-level_order', 'last_name')
    context['carded_b'] = team_players.filter(level="B", is_carded=True).order_by('position', '-level_order', 'last_name')
    context['protected_veterans'] = team_players.filter(Q(is_1h_c=True)|Q(is_1h_p=True)|Q(is_1h_pos=True)|Q(is_reserve=True)).order_by('position', '-level_order', 'last_name')
    context['num_owned'] = team_players.count()
    context['num_uncarded'] = team_players.filter(is_carded=False).count()
    context['num_35_man'] = context['on_35_man'].count()
    return render(request, 'team_protect.html', context)

def team_detail(request, abbreviation):
    context = utils.build_context(request)
    context['team'] = get_object_or_404(models.Team, abbreviation__icontains=abbreviation)
    team_players = models.Player.objects.filter(team=context['team'])
    context['num_owned'] = team_players.count()
    context['by_level'] = team_players.order_by('-level_order').values('level').annotate(Count('level'))
    context['by_position'] = team_players.order_by('position').values('position').annotate(Count('position'))
    context['players'] = team_players.order_by('position', '-level_order', 'last_name', 'first_name')
    return render(request, 'team.html', context)

def team_livestat_detail(request, abbreviation):
    context = utils.build_context(request)
    context['team'] = get_object_or_404(models.Team, abbreviation__icontains=abbreviation)
    team_players = models.Player.objects.filter(team=context['team'])
    context['num_owned'] = models.Player.objects.filter(team=context['team']).count()
    context['hitters'] = team_players.exclude(position="P").order_by('position', '-level_order', 'last_name', 'first_name')
    context['pitchers'] = team_players.filter(position="P").order_by('-level_order', 'last_name', 'first_name')
    return render(request, 'team_livestat.html', context)

def unprotected(request):
    context = utils.build_context(request)

    context['owned_hitters'] = models.Player.objects.filter(level="V", team__isnull=False, ls_plate_appearances__gte=1, is_mlb_roster=False, is_1h_c=False, is_1h_p=False, is_1h_pos=False, is_35man_roster=False, is_reserve=False).exclude(position="P").order_by('position', '-level_order', 'last_name', 'first_name')
    context['owned_pitchers'] = models.Player.objects.filter(level="V", team__isnull=False, ls_g__gte=1, is_mlb_roster=False, is_1h_c=False, is_1h_p=False, is_1h_pos=False, is_35man_roster=False, is_reserve=False).order_by('-level_order', 'last_name', 'first_name')

    return render(request, 'unprotected.html', context)

def available_livestat(request):
    context = utils.build_context(request)
    context['hitters'] = models.Player.objects\
        .filter(
            Q(level="V", team__isnull=True, ls_plate_appearances__gte=1)|\
            Q(level__in=['A', 'B'], team__isnull=True, ls_plate_appearances__gte=1, is_carded=True))\
    .exclude(position="P")\
    .order_by('position', '-level_order', 'last_name', 'first_name')

    context['pitchers'] = models.Player.objects\
        .filter(
            Q(level="V", team__isnull=True, ls_ip__gte=1, position="P")|\
            Q(level__in=['A', 'B'], team__isnull=True, ls_ip__gte=1, is_carded=True, position="P"))\
    .order_by('-level_order', 'last_name', 'first_name')

    context['owned_hitters'] = models.Player.objects.filter(level="V", team__isnull=False, ls_plate_appearances__gte=1, is_mlb_roster=False, is_1h_c=False, is_1h_p=False, is_1h_pos=False, is_35man_roster=False, is_reserve=False).exclude(position="P").order_by('position', '-level_order', 'last_name', 'first_name')
    context['owned_pitchers'] = models.Player.objects.filter(level="V", team__isnull=False, ls_g__gte=1, is_mlb_roster=False, is_1h_c=False, is_1h_p=False, is_1h_pos=False, is_35man_roster=False, is_reserve=False).order_by('-level_order', 'last_name', 'first_name')

    context['aa_hitters'] = models.Player.objects.filter(level="B", team__isnull=True, ls_plate_appearances__gte=1).exclude(position="P").order_by('position', '-level_order', 'last_name', 'first_name')
    context['aa_pitchers'] = models.Player.objects.filter(level="B", team__isnull=True, ls_g__gte=1).order_by('-level_order', 'last_name', 'first_name')

    return render(request, 'available_livestat.html', context)

def all_csv(request):
    team_players = models.Player.objects.filter(is_owned=True).order_by('team', '-is_35man_roster', 'position', '-level_order', 'last_name', 'first_name').values(*settings.CSV_COLUMNS)

    # Create the HttpResponse object with the appropriate CSV header.
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="all-teams-%s.csv"' % (datetime.datetime.now().isoformat().split('.')[0])
    writer = csv.DictWriter(response, fieldnames=settings.CSV_COLUMNS)
    writer.writeheader()
    for p in team_players:
        for k,v in p.items():
            if v == True:
                p[k] = "x"
            if v == False:
                p[k] = ""
        if p['defense']:
            p['defense'] = ",".join([f"{d.split('-')[0]}{d.split('-')[2]}" for d in p['defense']])
        else:
            p['defense'] = ""
        writer.writerow(p)
    return response

def team_csv(request, abbreviation):
    team = get_object_or_404(models.Team, abbreviation__icontains=abbreviation)
    team_players = models.Player.objects.filter(team=team).order_by('-is_mlb_roster', '-is_aaa_roster', 'position', '-level_order', 'last_name', 'first_name').values(*settings.CSV_COLUMNS)

    # Create the HttpResponse object with the appropriate CSV header.
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="%s-%s.csv"' % (abbreviation, datetime.datetime.now().isoformat().split('.')[0])
    writer = csv.DictWriter(response, fieldnames=settings.CSV_COLUMNS)
    writer.writeheader()
    for p in team_players:
        for k,v in p.items():
            if v == True:
                p[k] = "x"
            if v == False:
                p[k] = ""
        if p['defense']:
            p['defense'] = ",".join([f"{d.split('-')[0]}{d.split('-')[2]}" for d in p['defense']])
        else:
            p['defense'] = ""
        writer.writerow(p)
    return response

def team_other(request, abbreviation):
    context = utils.build_context(request)
    team = get_object_or_404(models.Team, abbreviation__icontains=abbreviation)
    context['team'] = team
    context['num_owned'] = models.Player.objects.filter(team=team).count()
    context['trades'] = models.TradeReceipt.objects.filter(team=team, trade__isnull=False).order_by('-trade__date')
    context['picks'] = models.DraftPick.objects.filter(team=team).order_by('-year', 'season', 'draft_type', 'draft_round', 'pick_number')
    return render(request, 'team_other.html', context)

def team_simple(request, abbreviation):
    context = utils.build_context(request)
    context['team'] = get_object_or_404(models.Team, abbreviation__icontains=abbreviation)
    context['players'] = models.Player.objects.filter(team=context['team']).order_by('last_name', 'first_name').values('last_name', 'first_name', 'level', 'position', 'id')
    return render(request, 'team_simple.html', context)

def trades(request):
    context = utils.build_context(request)
    context['archived_trades'] = models.TradeSummary.objects.all()
    context['trades'] = models.Trade.objects.all().order_by('-date')
    return render(request, 'trade_list.html', context)

def live_draft_admin(request, year, season, draft_type):
    context = utils.build_context(request)
    context['picks'] = models.DraftPick.objects.filter(year=year, season=season, draft_type=draft_type)

    if draft_type == "aa":
        context['players'] = json.dumps(["%(name)s (%(position)s)" % p for p in models.Player.objects.filter(is_owned=False, level="B").values('name', 'position')])

    if draft_type == "open":
        context['players'] = []
        for p in models.Player.objects.filter(is_owned=False).values('name', 'position'):
            context['players'].append("%(name)s (%(position)s)" % p )
    
        for p in models.Player.objects.filter(level="V", team__isnull=False, is_mlb_roster=False, is_1h_c=False, is_1h_p=False, is_1h_pos=False, is_35man_roster=False, is_reserve=False).values('name', 'position'):
            context['players'].append("%(name)s (%(position)s)" % p )

        context['players'] = json.dumps(players)

    context['year'] = year
    context['season'] = season
    context['draft_type'] = draft_type

    return render(request, "live_draft_admin.html", context)

def live_draft_watch(request, year, season, draft_type):
    context = utils.build_context(request)
    context['made_picks'] = models.DraftPick.objects\
                                .filter(Q(player_name__isnull=False)|Q(player__isnull=False))\
                                .filter(year=year, season=season, draft_type=draft_type)\
                                .order_by("year", "-season", "draft_type", "-draft_round", "-pick_number")
    context['upcoming_picks'] = models.DraftPick.objects\
                                .filter(year=year, season=season, draft_type=draft_type)\
                                .exclude(Q(player_name__isnull=False)|Q(player__isnull=False))
    context['year'] = year
    context['season'] = season
    context['draft_type'] = draft_type

    return render(request, "live_draft_watch.html", context)

def live_draft_api(request, year, season, draft_type):
    context = {}
    context['picks'] = [p.to_dict() for p in models.DraftPick.objects.filter(year=year, season=season, draft_type=draft_type)]
    context['year'] = year
    context['season'] = season
    context['draft_type'] = draft_type

    return JsonResponse(context)

def interesting(request):
    context = utils.build_context(request)
    context['aa_avail'] = models.Player.objects.filter(is_interesting=True, is_owned=False, is_carded=False)
    context['aa_taken'] = models.Player.objects.filter(is_interesting=True, is_owned=True, is_carded=False)
    context['open_avail'] = models.Player.objects.filter(is_interesting=True, is_owned=False, is_carded=True)
    context['open_taken'] = models.Player.objects.filter(is_interesting=True, is_owned=True, is_carded=True)
    return render(request, 'interesting.html', context)

@csrf_exempt
def draft_action(request, pickid):
    playerid = None
    name = None

    if request.GET.get('name', None):
        name = request.GET['name']

    if request.GET.get('playerid', None):
        playerid = request.GET('playerid')

    draftpick = get_object_or_404(models.DraftPick, pk=pickid)

    if playerid:
        draftpick.player = get_object_or_404(models.Player, pk=playerid)
        draftpick.player.team = draftpick.team
        draftpick.player.save()
        draftpick.save()

    if name:
        if "(" in name:
            name = name.split('(')[0].strip()
        ps = models.Player.objects.filter(name=name)
        if len(ps) == 1:
            draftpick.player = ps[0]
            draftpick.player.team = draftpick.team
            draftpick.player.save()
        else:
            draftpick.player_name = name
        draftpick.save()

    if not name and not playerid:
        if draftpick.player:
            draftpick.player.team = None
            draftpick.player.save()
            draftpick.player = None
    
        if draftpick.player_name:
            draftpick.player_name = None

        draftpick.save()
    return HttpResponse('ok')

def player_list(request):
    is_carded = request.GET.get('is_carded', None)
    is_owned = request.GET.get('is_owned', None)
    ids = request.GET.get('ids', None)

    query = models.Player.objects

    if ids:
        query = query.filter(Q(fg_id__in=ids.split(','))|Q(fg_id__isnull=True))

    if is_carded:
        query = query.filter(is_carded=utils.str_to_bool(is_carded))

    if is_owned:
        query = query.filter(is_owned=utils.str_to_bool(is_owned))

    payload = [{"name": p.name, "fg_id": p.fg_id, "is_carded": p.is_carded, "is_owned": p.is_owned, "level": p.level, "age": p.age, "position": p.position, "def": p.defense_display(), "team": p.team_display(), "amateur": p.is_amateur} for p in query]


    return JsonResponse(payload, safe=False)

def search(request):
    def to_bool(b):
        if b.lower() in ['y','yes', 't', 'true', 'on']:
            return True
        return False

    context = utils.build_context(request)

    query = models.Player.objects.all()

    if request.GET.get('protected', None):
        protected = request.GET['protected']
        if protected.lower() != "":
            if to_bool(protected) == False:
                query = query.filter(Q(is_1h_c=False), Q(is_1h_p=False), Q(is_1h_pos=False), Q(is_35man_roster=False), Q(is_reserve=False))
            else:
                query = query.filter(
                    Q(is_1h_c=True)|\
                    Q(is_1h_p=True)|\
                    Q(is_1h_pos=True)|\
                    Q(is_35man_roster=True)|\
                    Q(is_reserve=True)
                ) 

            context['protected'] = protected

    if request.GET.get('name', None):
        name = request.GET['name']
        query = query.filter(name__search=name)
        context['name'] = name

    if request.GET.get('position', None):
        position = request.GET['position']
        if position.lower() not in ["", "h"]:
            query = query.filter(position__icontains=position)
            context['position'] = position
        elif position.lower() == "h":
            query = query.exclude(position="P")
            context['position'] = position

    if request.GET.get('level', None):
        level = request.GET['level']
        if level.lower() != "":
            query = query.filter(level=level)
            context['level'] = level

    if request.GET.get('reliever', None):
        reliever = request.GET['reliever']
        if reliever.lower() != "":
            query = query.filter(is_relief_eligible=to_bool(reliever))
            if to_bool(reliever) == False:
                query = query.filter(starts__isnull=False).exclude(starts=0)
            context['reliever'] = reliever

    if request.GET.get('prospect', None):
        prospect = request.GET['prospect']
        if prospect.lower() != "":
            query = query.filter(is_prospect=to_bool(prospect))
            context['prospect'] = prospect

    if request.GET.get('owned', None):
        owned = request.GET['owned']
        if owned.lower() != "":
            query = query.filter(is_owned=to_bool(owned))
            context['owned'] = owned

    if request.GET.get('carded', None):
        carded = request.GET['carded']
        if carded.lower() != "":
            query = query.filter(is_carded=to_bool(carded))
            context['carded'] = carded

    if request.GET.get('amateur', None):
        amateur = request.GET['amateur']
        if amateur.lower() != "":
            query = query.filter(is_amateur=to_bool(amateur))
            context['amateur'] = amateur

    query = query.order_by("level", "last_name")

    if request.GET.get('csv', None):
        c = request.GET['csv']
        if c.lower() in ['y', 'yes', 't', 'true']:
            query = query.values(*settings.CSV_COLUMNS)
            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = 'attachment; filename="search-%s.csv"' % (datetime.datetime.now().isoformat().split('.')[0])
            writer = csv.DictWriter(response, fieldnames=settings.CSV_COLUMNS)
            writer.writeheader()
            for p in query:
                writer.writerow(p)
            return response

    paginator = Paginator(query, 1000)
    page = request.GET.get('page')

    context['players'] = paginator.get_page(page)
    return render(request, "search.html", context)