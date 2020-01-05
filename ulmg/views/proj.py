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

def index(request):
    context = utils.build_context(request)
    context = utils.build_context(request)
    context['hitters'] = models.Player.objects\
        .filter(
            Q(level="V", team__isnull=True, ps_pa__gte=1, ps_is_mlb=True)|\
            Q(level__in=['A', 'B'], team__isnull=True, ps_pa__gte=1, ps_is_mlb=True))\
    .exclude(position="P")\
    .order_by('position', '-level_order', 'last_name', 'first_name')

    context['pitchers'] = models.Player.objects\
        .filter(
            Q(level="V", team__isnull=True, ps_ip__gte=1, position="P", ps_is_mlb=True)|\
            Q(level__in=['A', 'B'], team__isnull=True, ps_ip__gte=1, position="P", ps_is_mlb=True))\
    .order_by('-level_order', 'last_name', 'first_name')

    return render(request, 'proj/index.html', context)

def search(request):
    def to_bool(b):
        if b.lower() in ['y','yes', 't', 'true', 'on']:
            return True
        return False

    context = utils.build_context(request)

    query = models.Player.objects.filter(ps_is_mlb=True)

    if request.GET.get('protected', None):
        protected = request.GET['protected']
        if protected.lower() != "":
            if to_bool(protected) == False:
                query = query.filter(Q(is_1h_c=False), Q(is_1h_p=False), Q(is_1h_pos=False), Q(is_35man_roster=False), Q(is_reserve=False)).exclude(level="B")
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
        query = query.filter(name__icontains=name)
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
    return render(request, "proj/search.html", context)