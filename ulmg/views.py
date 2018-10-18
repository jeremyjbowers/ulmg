from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import render_to_response, get_object_or_404
from django.db.models import Count, Avg, Sum, Max, Min, Q
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator

from ulmg import models, utils

@csrf_exempt
def player_action(request, playerid, action):
    message = "I don't understand this action!"

    if action == "to_mlb":
        message = "adding %s to mlb roster" % playerid
        p = get_object_or_404(models.Player, id=playerid)
        p.is_mlb_roster = True
        p.is_aaa_roster = False
        p.save()

    if action == "to_aaa":
        message = "adding %s to aaa roster" % playerid
        p = get_object_or_404(models.Player, id=playerid)
        p.is_mlb_roster = False
        p.is_aaa_roster = True
        p.save()

    if action == "off_roster":
        message = "removing %s from rosters" % playerid
        p = get_object_or_404(models.Player, id=playerid)
        p.is_mlb_roster = False
        p.is_aaa_roster = False
        p.save()

    if action == "drop":
        message = "dropping %s" % playerid
        p = get_object_or_404(models.Player, id=playerid)
        p.is_mlb_roster = False
        p.is_aaa_roster = False
        p.team = None
        p.is_owned = False
        p.save()

    print(message)
    return HttpResponse(message)

def index(request):
    context = utils.build_context(request)
    context['rand_prospect'] = models.Player.objects.filter(is_owned=False, is_prospect=True).order_by('?')[0:6]
    context['rand_hit'] = models.Player.objects.filter(position__in=["IF", "OF", "IF/OF", "C"], is_owned=False, stats__isnull=False).order_by('?')[0:6]
    context['rand_pitch'] = models.Player.objects.filter(is_owned=False, position="P", stats__isnull=False).order_by('?')[0:6]
    context['carded_positions'] = models.Player.objects.filter(is_carded=True).order_by('position').values('position').annotate(Count('position'))
    context['uncarded_positions'] = models.Player.objects.filter(is_carded=False).order_by('position').values('position').annotate(Count('position'))

    return render_to_response('index.html', context=context)

def team_detail(request, abbreviation):
    context = utils.build_context(request)
    context['team'] = get_object_or_404(models.Team, abbreviation__icontains=abbreviation)

    team_players = models.Player.objects.filter(team=context['team'])
    context['num_owned'] = team_players.count()

    context['mlb_roster'] = team_players.filter(is_mlb_roster=True).order_by("position","-level", "last_name")
    context['aaa_roster'] = team_players.filter(is_aaa_roster=True).order_by("position","-level", "last_name")

    context['eligible'] = team_players.filter(level__in=["A", "V"], is_mlb_roster=False, is_aaa_roster=False).order_by("position","-level", "last_name")
    context['ineligible'] = team_players.filter(level="B").exclude(Q(is_aaa_roster=True)|Q(is_mlb_roster=True)).order_by("position", "last_name")
    context['num_rostered'] = team_players.filter(Q(is_aaa_roster=True)|Q(is_mlb_roster=True)).count()

    context['mlb_count'] = team_players.filter(is_mlb_roster=True).count()
    context['aaa_count'] = team_players.filter(is_aaa_roster=True).count()
    context['aa_count'] = team_players.filter(level__in=["B"], is_mlb_roster=False, is_aaa_roster=False).count()

    context['by_position'] = team_players.order_by('position').values('position').annotate(Count('position'))
    context['by_level'] = team_players.order_by('level').values('level').annotate(Count('level'))

    return render_to_response('team_detail.html', context=context)

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
        if position.lower() != "":
            query = query.filter(position=position)
            context['position'] = position

    if request.GET.get('level', None):
        level = request.GET['level']
        if level.lower() != "":
            query = query.filter(level=level)
            context['level'] = level

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
    paginator = Paginator(query, 100)
    page = request.GET.get('page')

    context['players'] = paginator.get_page(page)
    return render_to_response("player_list.html", context=context)