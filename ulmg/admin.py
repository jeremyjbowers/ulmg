from django.contrib import admin
import nested_admin
from reversion.admin import VersionAdmin

from ulmg.models import Team, Player

@admin.register(Team)
class TeamAdmin(VersionAdmin):
    model = Team
    list_display = ["city", "division", "owner", 'owner_email']
    list_editable = ['division']

@admin.register(Player)
class PlayerAdmin(VersionAdmin):
    model = Player
    readonly_fields = ["name", "is_owned", "is_prospect", "age"]
    list_display = ["name", "age", "is_owned", "is_prospect", "is_carded", "team", "level", "position", 'fg_prospect_rank', 'ba_prospect_rank', 'mlb_prospect_rank']
    list_filter = ["is_owned", "is_prospect", "is_carded", "team", "level", "position"]
    list_editable = []
    search_fields = ["name"]