from django.conf import settings
from ulmg import models
from ulmg.cache_utils import is_valkey_active


def nav(request):
    """Provide global nav data regardless of authentication."""
    context = {
        "teamnav": models.Team.objects.all().order_by("division", "abbreviation"),
        "draftnav": getattr(settings, "DRAFTS", []),
        "my_team": None,
        "current_season_type": getattr(settings, "CURRENT_SEASON_TYPE", "offseason"),
        "valkey_active": is_valkey_active(),
    }
    if request.user.is_authenticated:
        try:
            owner = models.Owner.objects.get(user=request.user)
            context["my_team"] = models.Team.objects.get(owner_obj=owner)
        except (models.Owner.DoesNotExist, models.Team.DoesNotExist):
            context["my_team"] = None
    return context


