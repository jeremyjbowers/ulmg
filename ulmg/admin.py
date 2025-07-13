from django.contrib import admin
from django.contrib.admin import ModelAdmin
from django.contrib.admin.widgets import FilteredSelectMultiple
from django.contrib.auth.models import User
from django.forms import ModelForm, DateField
from django.forms.widgets import SelectDateWidget
from django.db.models import Q
from datetime import datetime

from ulmg.models import (
    Team,
    Player,
    DraftPick,
    Trade,
    TradeReceipt,
    Wishlist,
    WishlistPlayer,
    Owner,
    ProspectRating,
    Event,
    Occurrence,
    Venue,
    PlayerStatSeason,
    MagicLinkToken,
    TradeSummary,
    Transaction,
)

# Configure admin site
admin.site.site_title = "The ULMG"
admin.site.site_header = "The ULMG: Admin"
admin.site.index_title = "Administer The ULMG Website"


class CurrentSeasonMLBFilter(admin.SimpleListFilter):
    title = 'MLB Status (Current Season)'
    parameter_name = 'current_mlb'

    def lookups(self, request, model_admin):
        return (
            ('yes', 'MLB'),
            ('no', 'Not MLB'),
        )

    def queryset(self, request, queryset):
        current_season = datetime.now().year
        if self.value() == 'yes':
            return queryset.filter(
                playerstatseason__season=current_season,
                playerstatseason__classification='1-majors'
            ).distinct()
        if self.value() == 'no':
            return queryset.exclude(
                playerstatseason__season=current_season,
                playerstatseason__classification='1-majors'
            ).distinct()


class CurrentSeasonCardedFilter(admin.SimpleListFilter):
    title = 'Carded Status (Current Season)'
    parameter_name = 'current_carded'

    def lookups(self, request, model_admin):
        return (
            ('yes', 'Carded'),
            ('no', 'Not Carded'),
        )

    def queryset(self, request, queryset):
        current_season = datetime.now().year
        if self.value() == 'yes':
            return queryset.filter(
                playerstatseason__season=current_season,
                playerstatseason__carded=True
            ).distinct()
        if self.value() == 'no':
            return queryset.exclude(
                playerstatseason__season=current_season,
                playerstatseason__carded=True
            ).distinct()


class CurrentSeasonInjuredFilter(admin.SimpleListFilter):
    title = 'Injured Status (Current Season)'
    parameter_name = 'current_injured'

    def lookups(self, request, model_admin):
        return (
            ('yes', 'Injured'),
            ('no', 'Not Injured'),
        )

    def queryset(self, request, queryset):
        current_season = datetime.now().year
        if self.value() == 'yes':
            return queryset.filter(
                playerstatseason__season=current_season,
                playerstatseason__is_injured=True
            ).distinct()
        if self.value() == 'no':
            return queryset.exclude(
                playerstatseason__season=current_season,
                playerstatseason__is_injured=True
            ).distinct()


class CurrentSeasonMLBOrgFilter(admin.SimpleListFilter):
    title = 'MLB Organization (Current Season)'
    parameter_name = 'current_mlb_org'

    def lookups(self, request, model_admin):
        # Get unique MLB organizations from current season
        current_season = datetime.now().year
        orgs = PlayerStatSeason.objects.filter(
            season=current_season,
            mlb_org__isnull=False
        ).values_list('mlb_org', flat=True).distinct()
        return [(org, org) for org in sorted(orgs) if org]

    def queryset(self, request, queryset):
        current_season = datetime.now().year
        if self.value():
            return queryset.filter(
                playerstatseason__season=current_season,
                playerstatseason__mlb_org=self.value()
            ).distinct()


@admin.register(PlayerStatSeason)
class PlayerStatSeasonAdmin(admin.ModelAdmin):
    model = PlayerStatSeason
    list_display = ["player", "season", "classification", "level", "carded", "owned", "is_mlb", "mlb_org"]
    list_filter = [
        "season", 
        "classification", 
        "level", 
        "carded", 
        "owned", 
        "is_mlb", 
        "is_injured", 
        "mlb_org",
        "is_starter",
        "is_bench"
    ]
    search_fields = ["player__name", "season", "classification", "level", "mlb_org"]
    autocomplete_fields = ["player"]
    readonly_fields = ["created", "last_modified"]
    
    class Media:
        css = {
            'all': ('admin/css/widgets.css',)
        }
    
    def get_readonly_fields(self, request, obj=None):
        if obj:  # editing an existing object
            return self.readonly_fields + ["player", "season", "classification"]
        return self.readonly_fields
    
    fieldsets = (
        (
            "Basic Info",
            {
                "description": "Season-specific player information. These fields track attributes that change by season rather than permanent player characteristics.",
                "fields": (
                    "player",
                    ("season", "classification", "level"),
                    ("minors", "owned", "carded"),
                ),
            },
        ),
        (
            "MLB Status",
            {
                "description": "Major League Baseball status and roster information for this season.",
                "fields": (
                    # ("is_umlb", "is_amateur"),
                    ("is_ulmg_mlb_roster", "is_ulmg_aaa_roster", "is_ulmg_35man_roster"),
                    # ("is_mlb40man", "mlb_org"),
                ),
            },
        ),
        (
            "Roster Position",
            {
                "classes": ("collapse",),
                "description": "Current roster position and role information.",
                "fields": (
                    # ("is_starter", "is_bench", "is_player_pool"),
                    # ("is_bullpen", "role", "role_type"),
                    ("role", "role_type"),
                    "roster_status",
                ),
            },
        ),
        (
            "Health",
            {
                "classes": ("collapse",),
                "description": "Injury status and health information.",
                "fields": (
                    "is_injured",
                    "injury_description",
                ),
            },
        ),
        (
            "Stats",
            {
                "classes": ("collapse",),
                "description": "Statistical performance data for this season.",
                "fields": (
                    "hit_stats",
                    "pitch_stats",
                ),
            },
        ),
    )


@admin.register(Venue)
class VenueAdmin(admin.ModelAdmin):
    model = Venue
    exclude = []
    list_display = ["name", "mlb_team", "team", "park_factor"]


class OccurrenceInline(admin.StackedInline):
    model = Occurrence
    exclude = ("active", "season")
    min_num = 1
    extra = 0


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    model = Event
    list_display = ["title", "description"]
    search_fields = ["title", "description"]
    inlines = [OccurrenceInline]


@admin.register(ProspectRating)
class ProspectRatingAdmin(admin.ModelAdmin):
    """
    year = models.CharField(max_length=4)
    player = models.ForeignKey(Player, on_delete=models.SET_NULL, null=True)
    player_name = models.CharField(max_length=255, null=True, blank=True)

    skew = models.DecimalField(max_digits=4, decimal_places=1, blank=True, null=True)
    med = models.DecimalField(max_digits=4, decimal_places=1, blank=True, null=True)
    avg = models.DecimalField(max_digits=4, decimal_places=1, blank=True, null=True)

    law = models.IntegerField(blank=True, null=True)
    ba = models.IntegerField(blank=True, null=True)
    bp = models.IntegerField(blank=True, null=True)
    mlb = models.IntegerField(blank=True, null=True)
    fg = models.IntegerField(blank=True, null=True)
    p365 = models.IntegerField(blank=True, null=True)
    plive = models.IntegerField(blank=True, null=True)
    p1500 = models.IntegerField(blank=True, null=True)
    ftrax = models.IntegerField(blank=True, null=True)
    cbs = models.IntegerField(blank=True, null=True)
    espn = models.IntegerField(blank=True, null=True)
    """

    model = ProspectRating
    list_display = ["player", "year", "avg"]
    list_filter = ["year"]
    search_fields = ["player", "player_name"]
    autocomplete_fields = ["player"]


@admin.register(Owner)
class OwnerAdmin(admin.ModelAdmin):
    model = Owner
    list_display = ["user", "name", "email"]


@admin.register(Wishlist)
class WishlistAdmin(admin.ModelAdmin):
    model = Wishlist


@admin.register(WishlistPlayer)
class WishlistPlayerAdmin(admin.ModelAdmin):
    model = WishlistPlayer
    autocomplete_fields = ["player"]
    list_display = ["player", "owner_name", "rank", 'player_type', 'player_level', 'player_school', 'player_year', 'player_fv']
    list_filter = [
        "wishlist", 
        'player__level', 
        'tier', 
        'player__is_owned', 
        'player_type', 
        'player_level', 
        'player_year', 
        'player_fv',
        # Note: Season-specific filters like carded, injured, etc. are now in PlayerStatSeason
        # Use the Player admin with custom filters to find players by season-specific criteria
    ]
    list_editable = ['rank', 'player_type', 'player_level', 'player_school', 'player_year', 'player_fv']


class TradeReceiptInline(admin.TabularInline):
    model = TradeReceipt
    exclude = ("active",)
    autocomplete_fields = ["players", "team", "picks"]
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
    list_display = ["team", "trade"]
    list_filter = ["team"]
    autocomplete_fields = ["players", "picks", "team"]


@admin.register(Trade)
class TradeAdmin(admin.ModelAdmin):
    model = Trade
    inlines = [TradeReceiptInline]
    exclude = ("active", "season")


@admin.register(DraftPick)
class DraftPickAdmin(admin.ModelAdmin):
    model = DraftPick
    list_display = ["year", "season", "slug", "overall_pick_number", "team"]
    list_filter = ["team", "year", "season"]
    list_editable = []
    autocomplete_fields = ["player", "team", "original_team"]
    search_fields = [
        "player__name",
        "team__city",
        "team__abbreviation",
        "slug",
        "year",
        "season",
        "draft_type",
    ]
    fieldsets = (
        (
            None,
            {
                "fields": (
                    ("year", "season", "draft_type"),
                    "team",
                    ("player", "player_name"),
                    "skipped",
                    ("draft_round", "overall_pick_number", "pick_number"),
                ),
            },
        ),
    )


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    model = Team
    list_display = ["city", "division", "owner_obj"]
    list_filter = ["division"]
    search_fields = ["city", "abbreviation", "owner"]
    readonly_fields = ["active", "division"]
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "city",
                    "abbreviation",
                    "nickname",
                    "division",
                    "owner_obj",
                    ("owner", "owner_email"),
                    "championships",
                ),
            },
        ),
    )


class PlayerStatSeasonInline(admin.TabularInline):
    model = PlayerStatSeason
    extra = 0
    readonly_fields = ["created", "last_modified"]
    fields = [
        "season", 
        "classification", 
        "level", 
        "carded", 
        "owned", 
        "is_mlb", 
        "is_injured", 
        "mlb_org",
        "is_starter",
        "is_bench"
    ]
    
    def get_queryset(self, request):
        """Show most recent seasons first"""
        return super().get_queryset(request).order_by('-season', '-classification')


@admin.register(Player)
class PlayerAdmin(admin.ModelAdmin):
    model = Player
    inlines = [PlayerStatSeasonInline]
    
    def current_season_carded(self, obj):
        """Show if player is carded in current season"""
        current_season = datetime.now().year
        stat_season = obj.playerstatseason_set.filter(season=current_season).first()
        return stat_season.carded if stat_season else False
    current_season_carded.boolean = True
    current_season_carded.short_description = 'Carded (Current)'
    
    def current_season_mlb_org(self, obj):
        """Show player's current MLB organization"""
        current_season = datetime.now().year
        stat_season = obj.playerstatseason_set.filter(season=current_season).first()
        return stat_season.mlb_org if stat_season else None
    current_season_mlb_org.short_description = 'MLB Org (Current)'
    
    def current_season_injured(self, obj):
        """Show if player is injured in current season"""
        current_season = datetime.now().year
        stat_season = obj.playerstatseason_set.filter(season=current_season).first()
        return stat_season.is_injured if stat_season else False
    current_season_injured.boolean = True
    current_season_injured.short_description = 'Injured (Current)'
    
    list_display = [
        "last_name",
        "first_name",
        "is_owned",
        "team",
        "level",
        "current_season_carded",
        "current_season_mlb_org",
        "current_season_injured",
        'mlbam_id',
        'fg_id',
        'birthdate'
    ]
    list_filter = [
        "is_owned",
        "team",
        "level",
        "position",
        CurrentSeasonMLBFilter,
        CurrentSeasonCardedFilter,
        CurrentSeasonInjuredFilter,
        CurrentSeasonMLBOrgFilter,
    ]
    list_editable = ['mlbam_id','fg_id', 'birthdate']
    readonly_fields = ["name", "age"]
    search_fields = ["name", 'mlbam_id', 'fg_id', 'birthdate']
    autocomplete_fields = ["team"]
    fieldsets = (
        (
            "Biographical",
            {
                "fields": (
                    "name",
                    ("first_name", "last_name"),
                    ("birthdate", "raw_age"),
                    "position",
                    "level",
                    "team",
                ),
            },
        ),
        (
            "External IDs",
            {
                "fields": (
                    ("fg_id", "mlbam_id"),
                    ("ba_id", "bp_id", "bref_id"),
                    ("fantrax_id", "baseballcube_id", "perfectgame_id"),
                )
            },
        ),
        (
            "External URLs",
            {
                "classes": ("collapse",),
                "fields": (
                    ("ba_url", "bref_url", "fg_url"),
                    ("mlb_dotcom_url", "fantrax_url"),
                    "bref_img",
                )
            },
        ),
        (
            "ULMG Protection Status",
            {
                "classes": ("collapse",),
                "fields": (
                    ("is_ulmg_reserve",),
                    ("is_ulmg_1h_p", "is_ulmg_1h_c", "is_ulmg_1h_pos"),
                    ('is_ulmg_midseason_unprotected'),
                    ("is_ulmg_2h_draft", "is_ulmg_2h_p", "is_ulmg_2h_c", "is_ulmg_2h_pos"),
                    # ("is_protected", "cannot_be_protected", "covid_protected"),
                    # "is_trade_block",
                ),
            },
        ),
        (
            "Prospect Info",
            {
                "classes": ("collapse",),
                "fields": (
                    "is_prospect",
                    "league",
                    "prospect_rating_avg",
                    "class_year",
                    ("fg_fv", "fg_eta", "fg_org_rank"),
                    "notes",
                ),
            },
        ),
        (
            "Career Stats",
            {
                "classes": ("collapse",),
                "fields": (
                    ("cs_pa", "cs_gp", "cs_st", "cs_ip"),
                ),
            },
        ),
        (
            "Advanced",
            {
                "classes": ("collapse",),
                "fields": (
                    "is_owned", 
                    "defense", 
                    # "strat_ratings"
                ),
            },
        ),
    )


@admin.register(MagicLinkToken)
class MagicLinkTokenAdmin(admin.ModelAdmin):
    model = MagicLinkToken
    list_display = ["user", "token", "expires_at", "used", "active", "created"]
    list_filter = ["used", "active", "expires_at"]
    readonly_fields = ["token", "created", "last_modified"]
    search_fields = ["user__email", "user__username"]
