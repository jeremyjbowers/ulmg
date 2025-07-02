from django.contrib import admin
from django.urls import include, path

from ulmg import views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("django.contrib.auth.urls")),
    path("api/v1/player/scouting-report/<int:playerid>/", views.api.scouting_report),
    path("api/v1/wishlist/players/", views.api.get_wishlist_players),
    path("api/v1/player/", views.api.player_list),
    path(
        "api/v1/draft/live/<int:year>/<str:season>/<str:draft_type>/",
        views.api.draft_api,
    ),
    path(
        "api/v1/draft/watch/<int:year>/<str:season>/<str:draft_type>/",
        views.api.draft_watch_status,
    ),
    path("api/v1/player/<int:playerid>/<str:action>/", views.api.player_action),
    path("api/v1/draft/<str:pickid>/", views.api.draft_action),
    path("api/v1/wishlist/bulk/", views.api.wishlist_bulk_action),
    path(
        "api/v1/wishlist/note/add/<str:playerid>/", views.api.add_note_to_wishlistplayer
    ),
    path(
        "api/v1/wishlist/tags/delete/<str:playerid>/",
        views.api.delete_tag_from_wishlistplayer,
    ),
    path(
        "api/v1/wishlist/tags/add/<str:playerid>/", views.api.add_tag_to_wishlistplayer
    ),
    path("api/v1/wishlist/<str:playerid>/", views.api.wishlist_player_action),
    path("api/v1/trade/bulk/", views.api.trade_bulk_action),
    path("api/v1/player/bulk/", views.api.player_bulk_action),
    path("api/v1/player/autocomplete/", views.api.player_autocomplete),
    path("api/v1/detail/player/", views.api.player_detail),
    path("teams/csv/", views.csv.all_csv),
    path("teams/<str:abbreviation>/csv/", views.csv.team_csv),
    path("teams/<str:abbreviation>/other/", views.site.team_other),
    path("teams/<str:abbreviation>/", views.site.team_detail),
    path("trades/", views.site.trades),

    path("special/players/", views.special.player_util),
    path("special/trades/", views.special.trade_util),
    path("special/players/bulk/", views.special.special_bulk_add_players),
    path("players/trade-block/", views.site.trade_block),
    path("players/available/offseason/", views.site.player_available_offseason),
    path("players/available/midseason/", views.site.player_available_midseason),
    path("players/<int:playerid>/", views.site.player),
    path("players/search/", views.site.search_by_name),
    path("search/name/", views.site.search_by_name),
    path("search/filter/", views.site.filter_players),
    path("draft/live/players/owned/", views.api.player_owned),
    path(
        "draft/live/<int:year>/<str:season>/<str:draft_type>/edit/",
        views.site.draft_admin,
    ),
    path(
        "draft/live/<int:year>/<str:season>/<str:draft_type>/", views.site.draft_watch
    ),
    path("draft/<int:year>/<str:season>/<str:draft_type>/", views.site.draft_recap),
    path("my/<str:list_type>/draft/", views.my.my_draft_prep),
    path("my/<str:list_type>/draft/", views.my.my_draft_prep),
    path("my/wishlist/draft/beta/", views.my.my_wishlist_beta),
    path("", views.site.index),
]
