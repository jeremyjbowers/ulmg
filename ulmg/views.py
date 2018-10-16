from django.shortcuts import render_to_response, get_object_or_404
from django.db.models import Count, Avg, Sum, Max, Min
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator

from ulmg import models, utils

def index(request):
    context = utils.build_context(request)
    context['prospects'] = models.Player.objects.filter(is_owned=False, is_prospect=True).order_by('position', 'last_name')
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
    context['protected'] = team_players.filter(level="B").order_by("position", "last_name")
    context['unprotected'] = team_players.filter(level__in=["A", "V"]).order_by("position","-level", "last_name")
    context['num_rostered'] = team_players.filter(is_rostered=True).count()
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
        if position.lower() != "position":
            query = query.filter(position=position)
            context['position'] = position

    if request.GET.get('level', None):
        level = request.GET['level']
        if level.lower() != "level":
            query = query.filter(level=level)
            context['level'] = level

    if request.GET.get('prospect', None):
        prospect = to_bool(request.GET['prospect'])
        query = query.filter(is_prospect=prospect)
        context['prospect'] = prospect

    if request.GET.get('owned', None):
        owned = to_bool(request.GET['owned'])
        query = query.filter(is_owned=owned)
        context['owned'] = owned

    if request.GET.get('carded', None):
        carded = to_bool(request.GET['carded'])
        query = query.filter(is_carded=carded)
        context['carded'] = carded

    query = query.order_by('last_name')
    paginator = Paginator(query, 100)
    page = request.GET.get('page')

    context['players'] = paginator.get_page(page)
    return render_to_response("player_list.html", context=context)