from django.contrib import admin
from reversion.admin import VersionAdmin

from ulmg.models import Team, Player, DraftPick, Trade, TradeReceipt

class TradeReceiptInline(admin.TabularInline):
    model = TradeReceipt
    readonly_fields = ['players', 'picks', 'team', 'active']
    extra = 0

@admin.register(Trade)
class TradeAdmin(VersionAdmin):
    model = Trade
    inlines = [
        TradeReceiptInline
    ]

@admin.register(DraftPick)
class DraftPickAdmin(VersionAdmin):
    model = DraftPick
    list_display = ['year', 'season', 'draft_type', 'draft_round', 'pick_number', 'team']
    list_filter = list_display

@admin.register(Team)
class TeamAdmin(VersionAdmin):
    model = Team
    list_display = ["city", "division", "owner", 'owner_email']
    list_filter = ['division']
    list_editable = []

@admin.register(Player)
class PlayerAdmin(VersionAdmin):
    model = Player
    readonly_fields = ["name", "age"]
    list_display = ["name", "age", "is_owned", "is_prospect", "is_carded", "team", "level", "position", 'fg_prospect_rank', 'ba_prospect_rank', 'mlb_prospect_rank']
    list_filter = ["is_owned", "is_prospect", "is_carded", "team", "level", "position"]
    list_editable = []
    search_fields = ["name"]