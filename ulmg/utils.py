from ulmg import models
from django.conf import settings


def build_context(request):
    context = {}

    # to build the nav
    context['teamnav'] = models.Team.objects.all().values('abbreviation')
    context['draftnav'] = settings.DRAFTS

    # for showing stats
    context['advanced'] = False
    if request.GET.get('adv', None):
        context['advanced'] = True

    context['roster_tab'] = settings.TEAM_ROSTER_TAB

    context['protect_tab'] = settings.TEAM_PROTECT_TAB

    # for search
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