from django.shortcuts import render_to_response, get_object_or_404

from ulmg import models, utils

def index(request):
    context = utils.build_context(request)

    return render_to_response('index.html', context=context)

def team_detail(request, abbreviation):
    context = utils.build_context(request)
    context['team'] = get_object_or_404(models.Team, abbreviation__icontains=abbreviation)
    context['protected'] = models.Player.objects.filter(team=context['team'], level="B").order_by("position", "last_name")
    context['unprotected'] = models.Player.objects.filter(team=context['team'], level__in=["A", "V"]).order_by("position","-level", "last_name")

    return render_to_response('team_detail.html', context=context)