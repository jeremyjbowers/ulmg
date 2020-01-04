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

    if action == "to_35_man":
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
        p.is_reserve = False
        p.is_1h_c = False
        p.is_1h_p = False
        p.is_1h_pos = False
        p.is_35man_roster = False
        p.is_reserve = True
        p.save()


    if action == "is_1h_p":
        p = get_object_or_404(models.Player, id=playerid)
        old = models.Player.objects.filter(team=p.team, is_1h_p=True).update(is_1h_p=False)
        p.is_reserve = False
        p.is_1h_c = False
        p.is_1h_p = False
        p.is_1h_pos = False
        p.is_35man_roster = False
        p.is_1h_p = True
        p.save()

    if action == "is_1h_c":
        p = get_object_or_404(models.Player, id=playerid)
        old = models.Player.objects.filter(team=p.team, is_1h_c=True).update(is_1h_c=False)
        p.is_reserve = False
        p.is_1h_c = False
        p.is_1h_p = False
        p.is_1h_pos = False
        p.is_35man_roster = False
        p.is_1h_c = True
        p.save()

    if action == "is_1h_pos":
        p = get_object_or_404(models.Player, id=playerid)
        old = models.Player.objects.filter(team=p.team, is_1h_pos=True).update(is_1h_pos=False)
        p.is_reserve = False
        p.is_1h_c = False
        p.is_1h_p = False
        p.is_1h_pos = False
        p.is_35man_roster = False
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

def draft_api(request, year, season, draft_type):
    context = {}
    context['picks'] = [p.to_dict() for p in models.DraftPick.objects.filter(year=year, season=season, draft_type=draft_type)]
    context['year'] = year
    context['season'] = season
    context['draft_type'] = draft_type

    return JsonResponse(context)

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
        draftpick.player.is_mlb_roster = True
        draftpick.player.save()
        draftpick.save()

    if name:
        if "(" in name:
            name = name.split('(')[0].strip()
        ps = models.Player.objects.filter(name=name)
        if len(ps) == 1:
            draftpick.player = ps[0]
            draftpick.player.team = draftpick.team
            draftpick.player.is_mlb_roster = True
            draftpick.player.save()
        else:
            draftpick.player_name = name
        draftpick.save()

    if not name and not playerid:
        if draftpick.player:
            draftpick.player.team = None
            draftpick.player.is_mlb_roster = False
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

    query = query.order_by('position', '-level_order', 'last_name')

    context['hitters'] = query.exclude(position="P")
    context['pitchers'] = query.filter(position="P")
    return render(request, "search.html", context)