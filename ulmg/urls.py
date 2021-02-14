from django.contrib import admin
from django.urls import include, path

from ulmg import views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("django.contrib.auth.urls")),
    path("api/v1/player/", views.api.player_list),
    path("api/v1/draft/live/players/important/", views.api.bowers_important),
    path(
        "api/v1/draft/live/<int:year>/<str:season>/<str:draft_type>/",
        views.api.draft_api,
    ),
    path("api/v1/player/<int:playerid>/<str:action>/", views.api.player_action),
    path("api/v1/draft/<str:pickid>/", views.api.draft_action),
    path("api/v1/wishlist/bulk/", views.api.wishlist_bulk_action),
    path("api/v1/wishlist/<str:playerid>/", views.api.wishlist_player_action),
    path("teams/csv/", views.csv.all_csv),
    path("teams/<str:abbreviation>/csv/", views.csv.team_csv),
    path("teams/<str:abbreviation>/other/", views.site.team_other),
    path("teams/<str:abbreviation>/live/", views.site.team_realtime),
    path("teams/<str:abbreviation>/", views.site.team_detail),
    path("trades/", views.site.trades),
    path("prospect-rankings/<int:year>/", views.site.prospect_ranking_list),
    path("players/util/", views.site.player_util),
    path("players/available/midseason/", views.site.player_available_midseason),
    path("players/<int:playerid>/", views.site.player),
    path("players/search/", views.site.search),
    path("draft/live/players/owned/", views.api.player_owned),
    path("draft/live/bowers/aa/", views.site.bowers_aa),
    path(
        "draft/live/<int:year>/<str:season>/<str:draft_type>/edit/",
        views.site.draft_admin,
    ),
    path(
        "draft/live/<int:year>/<str:season>/<str:draft_type>/", views.site.draft_watch
    ),
    path("draft/<int:year>/<str:season>/<str:draft_type>/", views.site.draft_recap),
    path("my/wishlist/<str:list_type>/", views.my.my_wishlist),
    path("my/team/", views.my.my_team),
    path("", views.site.index),
]
