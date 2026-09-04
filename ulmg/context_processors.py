from django.conf import settings
from ulmg import models
from ulmg.cache_utils import is_valkey_active
from ulmg.utils import get_draft_prep_season_type, get_owner_for_user, get_team_for_owner


def nav(request):
    """Provide global nav data regardless of authentication."""
    owner = get_owner_for_user(request.user)
    context = {
        "teamnav": models.Team.objects.all().order_by("division", "abbreviation"),
        "draftnav": getattr(settings, "DRAFTS", []),
        "my_team": get_team_for_owner(owner),
        "current_season": getattr(settings, "CURRENT_SEASON", None),
        "current_season_type": getattr(settings, "CURRENT_SEASON_TYPE", "offseason"),
        "draft_prep_season": get_draft_prep_season_type(),
        "valkey_active": is_valkey_active(),
    }
    return context


