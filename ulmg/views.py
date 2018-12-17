import csv
import datetime

from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import render, get_object_or_404
from django.db.models import Count, Avg, Sum, Max, Min, Q
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
import ujson as json

from ulmg import models, utils


MINIMUM_VALUES = ['last_name', 'first_name', 'level', 'is_owned', 'is_prospect', 'is_carded', 'is_amateur', 'team', 'is_relief_eligible', 'starts', 'relief_innings_pitched', 'plate_appearances', 'birthdate', 'fg_url', 'bref_url', 'ba_url', 'mlb_url', 'position']
CURRENT_SEASON = "2019"

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
    context['rand_prospect'] = models.Player.objects.filter(is_owned=False, is_prospect=True).order_by('?')[0:6]
    context['rand_hit'] = models.Player.objects.filter(position__in=["IF", "OF", "IF/OF", "C"], is_owned=False, stats__isnull=False).order_by('?')[0:6]
    context['rand_pitch'] = models.Player.objects.filter(is_owned=False, position="P", stats__isnull=False).order_by('?')[0:6]
    context['carded_positions'] = models.Player.objects.filter(is_carded=True).order_by('position').values('position').annotate(Count('position'))
    context['uncarded_positions'] = models.Player.objects.filter(is_carded=False).order_by('position').values('position').annotate(Count('position'))

    return render(request, 'index.html', context)

def roster_team_detail(request, abbreviation):
    context = utils.build_context(request)
    context['team'] = get_object_or_404(models.Team, abbreviation__icontains=abbreviation)
    team_players = models.Player.objects.filter(team=context['team'])
    context['unrostered'] = team_players.filter(is_mlb_roster=False, is_aaa_roster=False, is_carded=True).order_by('position', '-level_order', 'last_name')
    context['mlb_roster'] = team_players.filter(is_mlb_roster=True, is_carded=True).order_by('position', '-level_order', 'last_name')
    context['num_mlb'] = context['mlb_roster'].count()
    context['aaa_roster'] = team_players.filter(is_aaa_roster=True, is_carded=True).order_by('position', '-level_order', 'last_name')
    context['num_owned'] = team_players.count()
    team_players = models.Player.objects.filter(team=context['team'])
    return render(request, 'team_roster.html', context)

def protect_team_detail(request, abbreviation):
    context = utils.build_context(request)
    context['team'] = get_object_or_404(models.Team, abbreviation__icontains=abbreviation)
    team_players = models.Player.objects.filter(team=context['team'])
    context['on_35_man'] = team_players.filter(is_35man_roster=True).order_by('position', '-level_order', 'last_name')
    context['unprotected'] = team_players.filter(level__in=['V', 'A'], is_carded=True, is_1h_c=False, is_1h_p=False, is_1h_pos=False, is_35man_roster=False, is_reserve=False).order_by('position', '-level_order', 'last_name')
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

def team_csv(request, abbreviation):
    team = get_object_or_404(models.Team, abbreviation__icontains=abbreviation)
    team_players = models.Player.objects.filter(team=team).order_by('position', '-level_order', 'last_name', 'first_name').values(*MINIMUM_VALUES)

    # Create the HttpResponse object with the appropriate CSV header.
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="%s-%s.csv"' % (abbreviation, datetime.datetime.now().isoformat().split('.')[0])
    writer = csv.DictWriter(response, fieldnames=MINIMUM_VALUES)
    writer.writeheader()
    for p in team_players:
        writer.writerow(p)
    return response

def team_other(request, abbreviation):
    context = utils.build_context(request)
    team = get_object_or_404(models.Team, abbreviation__icontains=abbreviation)
    context['team'] = team
    team_players = models.Player.objects.filter(team=context['team'])
    context['num_owned'] = team_players.count()
    context['trades'] = models.TradeReceipt.objects.filter(team=context['team']).order_by('-trade__date')
    context['picks'] = models.DraftPick.objects.filter(team=context['team'])
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

def search(request):
    def to_bool(b):
        if b.lower() in ['y','yes', 't', 'true', 'on']:
            return True
        return False

    context = utils.build_context(request)

    query = models.Player.objects.all()

    if request.GET.get('name', None):
        name = request.GET['name']
        query = query.filter(name__search=name)
        context['name'] = name

    if request.GET.get('position', None):
        position = request.GET['position']
        if position.lower() not in ["", "h"]:
            query = query.filter(position=position)
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

    query = query.order_by('position', "level", "last_name")

    if request.GET.get('csv', None):
        c = request.GET['csv']
        if c.lower() in ['y', 'yes', 't', 'true']:
            query = query.values(*MINIMUM_VALUES)
            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = 'attachment; filename="search-%s.csv"' % (datetime.datetime.now().isoformat().split('.')[0])
            writer = csv.DictWriter(response, fieldnames=MINIMUM_VALUES)
            writer.writeheader()
            for p in query:
                writer.writerow(p)
            return response

    paginator = Paginator(query, 1000)
    page = request.GET.get('page')

    context['players'] = paginator.get_page(page)
    return render(request, "player_list.html", context)