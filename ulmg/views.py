from django.shortcuts import render_to_response, get_object_or_404

from ulmg import models

def player_list(request):
    context = {}
    context['players'] = models.Player.objects.filter(active=True, owned=True).order_by("team", "position", "level", "last_name")

    return render_to_response('player_list.html', context=context)