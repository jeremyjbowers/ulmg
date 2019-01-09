from ulmg import models

TEAM_PROTECT_TAB=False
TEAM_ROSTER_TAB=True


def build_context(request):
    context = {}
    context['roster_tab'] = TEAM_ROSTER_TAB
    context['protect_tab'] = TEAM_PROTECT_TAB
    context['teamnav'] = models.Team.objects.all().values('abbreviation')
    context['value'] = False
    if request.GET.get('value', None):
        context['value'] = True
    queries_without_page = dict(request.GET)
    if queries_without_page.get('page', None):
        del queries_without_page['page']
    context['q_string'] = "&".join(['%s=%s' % (k,v[-1]) for k,v in queries_without_page.items()])
    return context