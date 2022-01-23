from django.contrib import admin

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
    Venue
)

admin.site.site_title = "The ULMG"
admin.site.site_header = "The ULMG: Admin"
admin.site.index_title = "Administer The ULMG Website"


@admin.register(Venue)
class VenueAdmin(admin.ModelAdmin):
    model = Venue
    exclude = []
    list_display = ["name", 'mlb_team', 'team', 'park_factor']


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
class WishlistPlayer(admin.ModelAdmin):
    model = WishlistPlayer
    list_display = ["player", "owner_name", "rank", "tier"]
    list_filter = ["wishlist"]


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


@admin.register(Player)
class PlayerAdmin(admin.ModelAdmin):
    model = Player
    list_display = [
        "last_name",
        "first_name",
        "is_owned",
        "team",
        "level",
    ]
    list_filter = [
        "is_owned",
        "team",
        "level",
        "position",
        "ls_is_mlb",
    ]
    list_editable = []
    readonly_fields = ["name", "age"]
    search_fields = ["name"]
    autocomplete_fields = ["team"]
    fieldsets = (
        (
            "Biographical",
            {
                "fields": (
                    "name",
                    ("first_name", "last_name"),
                    ("birthdate", "birthdate_qa", "raw_age"),
                    "position",
                    "level",
                    "team",
                    ("mlb_team", "mlb_team_abbr"),
                ),
            },
        ),
        (
            "External",
            {
                "fields": (
                    ("fg_id", "fg_url"),
                    ("bref_id", "bref_url"),
                    ("ba_id", "ba_url"),
                    "mlbam_id",
                    ("mlb_dotcom", "mlb_dotcom_url"),
                )
            },
        ),
        (
            "Roster",
            {
                "classes": ("collapse",),
                "fields": (("is_mlb_roster", "is_aaa_roster", "is_35man_roster"),),
            },
        ),
        (
            "Protection",
            {
                "classes": ("collapse",),
                "fields": (
                    ("is_reserve",),
                    ("is_1h_p", "is_1h_c", "is_1h_pos"),
                    ("is_2h_draft", "is_2h_p", "is_2h_c", "is_2h_pos"),
                    ("is_protected", "cannot_be_protected", "covid_protected"),
                ),
            },
        ),
        (
            "Live stats",
            {
                "classes": ("collapse",),
                "fields": (
                    ("is_starter", "is_bench", "is_player_pool"),
                    ("is_injured", "ls_is_mlb"),
                    "injury_description",
                    ("role",),
                    ("is_mlb40man", "is_bullpen"),
                ),
            },
        ),
        (
            "Prospect",
            {
                "classes": ("collapse",),
                "fields": (
                    ("is_prospect", "is_amateur"),
                    "league",
                    "prospect_rating_avg",
                    "class_year",
                    ("fg_fv", "fg_eta", "fg_org_rank"),
                    "notes",
                ),
            },
        ),
        (
            "Strat",
            {
                "classes": ("collapse",),
                "fields": (
                    ("strat_obtb_l", "strat_obtb_r"),
                ),
            },
        ),
        (
            "Advanced",
            {
                "classes": ("collapse",),
                "fields": (
                    "is_carded",
                    "is_owned",
                    'defense',
                    'stats'
                ),
            },
        ),
    )
