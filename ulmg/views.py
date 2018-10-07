from django.shortcuts import render_to_response, get_object_or_404

from ulmg import models

def team_detail(request, abbreviation):
    context = {}
    context['teams'] = models.Team.objects.all()
    context['team'] = get_object_or_404(models.Team, abbreviation__icontains=abbreviation)
    context['players'] = models.Player.objects.filter(active=True, owned=True, team=context['team']).order_by("position", "level", "last_name")

    return render_to_response('team_detail.html', context=context)

def all_teams(request):
    context = {}
    context['teams'] = models.Team.objects.all()
    context['players'] = models.Player.objects.filter(active=True, owned=True).order_by("team", "position", "level", "last_name")

    return render_to_response('all_teams.html', context=context)