from ulmg import models
from django.conf import settings


def build_context(request):
    context = {}
    context['roster_tab'] = settings.TEAM_ROSTER_TAB
    context['protect_tab'] = settings.TEAM_PROTECT_TAB
    context['teamnav'] = models.Team.objects.all().values('abbreviation')
    context['value'] = False
    if request.GET.get('value', None):
        context['value'] = True
    queries_without_page = dict(request.GET)
    if queries_without_page.get('page', None):
        del queries_without_page['page']
    context['q_string'] = "&".join(['%s=%s' % (k,v[-1]) for k,v in queries_without_page.items()])
    return context

def str_to_bool(possible_bool):
    if possible_bool:
        if possible_bool.lower() in ['y', 'yes', 't', 'true']:
            return True
        if possible_bool.lower() in ['n', 'no', 'f', 'false']:
            return False
    return None