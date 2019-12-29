from django.contrib import admin

from ulmg.models import Team, Player, DraftPick, Trade, TradeReceipt, ScoutingReport

admin.site.site_title = "The ULMG"
admin.site.site_header = "The ULMG: Admin"
admin.site.index_title = "Administer The ULMG Website"


class ScoutingReportInline(admin.StackedInline):
    model = ScoutingReport
    exclude = ('active', 'player_name', 'pv', 'risk', 'risk_name', 'season', 'evaluator', 'level', 'report_type')
    extra = 1
    fieldsets = (
        (None, {
            'fields': (
                ('date','fv','rank'),
                ('url', 'organization'),
                'report',
            ),
        }),
    )

class TradeReceiptInline(admin.TabularInline):
    model = TradeReceipt
    exclude = ('active',)
    autocomplete_fields = ['players', 'team', 'picks']
    min_num = 2
    max_num = 2
    extra = 2


@admin.register(TradeReceipt)
class TradeReceiptAdmin(admin.ModelAdmin):
    """
    trade = models.ForeignKey(Trade, on_delete=models.SET_NULL, null=True)
    team = models.ForeignKey(Team, on_delete=models.SET_NULL, null=True)
    players = models.ManyToManyField(Player, related_name="players", blank=True)
    picks = models.ManyToManyField(DraftPick, related_name="picks", blank=True)
    """
    model = TradeReceipt
    list_display = ['team', 'trade']
    list_filter = ['team']
    autocomplete_fields = ['players', 'picks', 'team']


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
    fieldsets = (
        (None, {
            'fields': (
                ('year','slug','season'),
                'team',
                ('player','player_name'),
                'pick_notes',
                'draft_type',
                ('draft_round','overall_pick_number','pick_number'),
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
                ('owner','owner_email'),
                'championships',
            ),
        }),
    )


@admin.register(Player)
class PlayerAdmin(admin.ModelAdmin):
    model = Player
    list_display = ["last_name", "first_name", "is_owned", "team", 'birthdate', 'is_amateur', 'fg_id', 'league', 'ls_is_mlb']
    list_filter = ["is_owned", "team", "level", "position", 'is_amateur', 'league', 'ls_is_mlb']
    list_editable = ['birthdate', 'league', 'is_amateur', 'fg_id']
    readonly_fields = ["name", "age"]
    search_fields = ["name"]
    autocomplete_fields = ['team']
    fieldsets = (
        ('Biographical', {
            'fields': (
                'name',
                ('first_name', 'last_name'),
                ('birthdate', 'age'),
                'position',
                ('level', 'is_amateur', 'league'),
                'team',
            ),
        }),
        ('External', {
            'fields': (
                'fg_id',
                'bref_id',
                'mlbam_id',
                'mlb_dotcom',
                'ba_id',
                'fg_url',
                'bref_url',
                'ba_url',
                'mlb_dotcom_url'
            )
        }),
        ('Player flags', {
            'classes': ('collapse',),
            'fields': (
                'is_carded',
                'is_owned',
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
                'is_2h_draft',
            )
        })
    )