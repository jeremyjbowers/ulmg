from ulmg import models


def build_context(request):
    context = {}
    context['teamnav'] = models.Team.objects.all().values('abbreviation')
    queries_without_page = dict(request.GET)
    if queries_without_page.get('page', None):
        del queries_without_page['page']
    context['q_string'] = "&".join(['%s=%s' % (k,v[-1]) for k,v in queries_without_page.items()])
    return context