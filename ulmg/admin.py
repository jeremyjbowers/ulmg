from django.contrib import admin

from ulmg.models import Team, Player, DraftPick, Trade, TradeReceipt

admin.site.site_title = "The ULMG"
admin.site.site_header = "The ULMG: Admin"
admin.site.index_title = "Administer The ULMG Website"


class TradeReceiptInline(admin.TabularInline):
    model = TradeReceipt
    exclude = ('active',)
    autocomplete_fields = ['players', 'team', 'picks']
    min_num = 2
    max_num = 2
    extra = 2

@admin.register(Trade)
class TradeAdmin(admin.ModelAdmin):
    model = Trade
    inlines = [
        TradeReceiptInline
    ]
    exclude = ('active',)

@admin.register(DraftPick)
class DraftPickAdmin(admin.ModelAdmin):
    model = DraftPick
    list_display = ['year', 'season', 'slug', 'overall_pick_number', 'team']
    list_filter = ['team', 'year', 'season']
    list_editable = []
    autocomplete_fields = ['player', 'team', 'original_team']
    search_fields = ['player__name', 'team__city', 'team__abbreviation', 'slug']
    readonly_fields = ['year', 'season', 'draft_type', 'draft_round', 'overall_pick_number', 'pick_number', 'original_team', 'slug']
    fieldsets = (
        (None, {
            'fields': (
                'year',
                'slug',
                'season',
                'team',
                'player',
                'pick_notes',
                'draft_type',
                'draft_round',
                'overall_pick_number',
                'pick_number',
                'original_team',
            ),
        }),
    )


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    model = Team
    list_display = ["city", "division", "owner", 'owner_email']
    list_filter = ['division']
    search_fields = ['city', 'abbreviation', 'owner']
    readonly_fields = ['active', 'division']
    fieldsets = (
        (None, {
            'fields': (
                'city',
                'abbreviation',
                'nickname',
                'division',
                'owner',
                'owner_email',
            ),
        }),
    )


@admin.register(Player)
class PlayerAdmin(admin.ModelAdmin):
    model = Player
    list_display = ["last_name", "first_name", "is_owned", 'is_carded', "team"]
    list_filter = ["is_owned", "is_prospect", "is_carded", "team", "level", "position"]
    list_editable = []
    readonly_fields = ["name", "age", 'is_relief_eligible', 'relief_innings_pitched', 'starts', 'plate_appearances','fg_prospect_fv','fg_prospect_rank','ba_prospect_rank','mlb_prospect_rank','ba_draft_rank', 'stats', 'steamer_predix']
    search_fields = ["name"]
    autocomplete_fields = ['team']
    fieldsets = (
        ('Biographical', {
            'fields': (
                'name',
                ('first_name', 'last_name'),
                'age',
                'birthdate',
                'position',
                'level',
                'team',
                'notes',
            ),
        }),
        ('Stats', {
            'fields': (
                'is_relief_eligible',
                'relief_innings_pitched',
                'starts',
                'plate_appearances',
            )
        }),
        ('Player flags', {
            'classes': ('collapse',),
            'fields': (
                'is_carded',
                'is_owned',
                'is_prospect',
                'is_amateur'
            )
        }),
        ('Roster', {
            'classes': ('collapse',),
            'fields': (
                'is_mlb_roster',
                'is_aaa_roster',
                'is_35man_roster',
            )
        }),
        ('Protection', {
            'classes': ('collapse',),
            'fields': (
                'is_reserve',
                'is_1h_p',
                'is_1h_c',
                'is_1h_pos',
                'is_2h_p',
                'is_2h_c',
                'is_2h_pos',
            )
        }),
        ('Prospect', {
            'classes': ('collapse',),
            'fields': (
                'fg_prospect_fv',
                'fg_prospect_rank',
                'ba_prospect_rank',
                'mlb_prospect_rank',
                'ba_draft_rank',
            )
        }),
        ('External', {
            'classes': ('collapse',),
            'fields': (
                'fg_id',
                'bref_id',
                'mlb_id',
                'ba_id',
                'fg_url',
                'bref_url',
                'mlb_url',
                'ba_url'
            )
        }),
        ('Advanced', {
            'classes': ('collapse',),
            'fields': (
                'stats',
                'steamer_predix',
            )
        }),
    )