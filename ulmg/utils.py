from ulmg import models


def build_context(request):
    context = {}
    context['teamnav'] = models.Team.objects.all().values('abbreviation')

    return context