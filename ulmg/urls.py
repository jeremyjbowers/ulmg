from django.contrib import admin
from django.urls import include, path
from django.contrib.auth import views as auth_views

from ulmg import views

urlpatterns = [
    # Custom admin login
    path("admin/login/", views.auth.admin_login_view, name="admin_login"),
    
    # Use default admin site
    path("admin/", admin.site.urls),
    
    # Authentication URLs - supports both password and magic link
    path("accounts/login/", views.auth.magic_login_request, name="login"),
    path("accounts/magic-verify/<str:token>/", views.auth.magic_login_verify, name="magic_login_verify"),
    path("admin/magic-login/", views.auth.admin_magic_login_request, name="admin_magic_login_request"),
    path("admin/magic-verify/<str:token>/", views.auth.admin_magic_login_verify, name="admin_magic_login_verify"),
    
    # Keep logout functionality - allow GET requests for simplicity
    path("accounts/logout/", auth_views.LogoutView.as_view(http_method_names=['get', 'post']), name="logout"),
    
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
    path("api/v1/players/owned/", views.api.owned_players),
    # MCP Phase 1 read-only JSON API (OwnerAPIToken Bearer auth)
    path("api/mcp/v1/season/", views.mcp.season_context),
    path("api/mcp/v1/teams/", views.mcp.teams_list),
    path("api/mcp/v1/roster/", views.mcp.my_roster),
    path("api/mcp/v1/compliance/", views.mcp.my_compliance),
    path("api/mcp/v1/teams/<str:abbreviation>/roster/", views.mcp.team_roster),
    path(
        "api/mcp/v1/teams/<str:abbreviation>/compliance/",
        views.mcp.team_compliance,
    ),
    path("api/mcp/v1/players/search/", views.mcp.players_search),
    path("api/mcp/v1/draft-picks/", views.mcp.draft_picks),
    path("api/mcp/v1/trades/", views.mcp.trades_list),
    path("api/mcp/v1/trade-block/", views.mcp.trade_block),
    path("api/mcp/v1/draft-pool/", views.mcp.draft_pool),
    path("api/mcp/v1/wishlist/", views.mcp.my_wishlist),
    path("teams/csv/", views.csv.all_csv),
    path("teams/<str:abbreviation>/csv/", views.csv.team_csv),
    path("teams/<str:abbreviation>/other/", views.site.team_other),
    path("teams/<str:abbreviation>/game/", views.roster.team_game, name="team_game"),
    path("teams/<str:abbreviation>/schedule/", views.schedule.team_schedule, name="team_schedule"),
    path("teams/<str:abbreviation>/schedule/<int:season>/", views.schedule.team_schedule, name="team_schedule"),
    path("teams/<str:abbreviation>/plan/<int:half>/", views.plan.team_plan, name="team_plan"),
    path("teams/<str:abbreviation>/plan/<int:half>/<int:season>/", views.plan.team_plan, name="team_plan"),
    path("teams/<str:abbreviation>/plan/<int:half>/edit/", views.plan.team_plan_edit, name="team_plan_edit"),
    path(
        "teams/<str:abbreviation>/plan/<int:half>/<int:season>/edit/",
        views.plan.team_plan_edit,
        name="team_plan_edit",
    ),
    path(
        "teams/<str:abbreviation>/plan/<int:half>/rotation/",
        views.plan.team_plan_rotation,
        name="team_plan_rotation",
    ),
    path(
        "teams/<str:abbreviation>/plan/<int:half>/<int:season>/rotation/",
        views.plan.team_plan_rotation,
        name="team_plan_rotation",
    ),
    path(
        "teams/<str:abbreviation>/plan/<int:half>/bullpen/",
        views.plan.team_plan_bullpen,
        name="team_plan_bullpen",
    ),
    path(
        "teams/<str:abbreviation>/plan/<int:half>/<int:season>/bullpen/",
        views.plan.team_plan_bullpen,
        name="team_plan_bullpen",
    ),
    path(
        "teams/<str:abbreviation>/plan/<int:half>/designation/",
        views.plan.team_plan_designation,
        name="team_plan_designation",
    ),
    path(
        "teams/<str:abbreviation>/plan/<int:half>/<int:season>/designation/",
        views.plan.team_plan_designation,
        name="team_plan_designation",
    ),
    path(
        "teams/<str:abbreviation>/plan/<int:half>/day/<int:day>/",
        views.plan.team_plan_day,
        name="team_plan_day",
    ),
    path(
        "teams/<str:abbreviation>/plan/<int:half>/<int:season>/day/<int:day>/",
        views.plan.team_plan_day,
        name="team_plan_day",
    ),
    path("teams/<str:abbreviation>/moves/", views.roster.team_roster_move, name="team_roster_move"),
    path("teams/<str:abbreviation>/moves/new/", views.roster.team_roster_move_choice, name="team_roster_move_choice"),
    path("teams/<str:abbreviation>/results/", views.season.team_results, name="team_results"),
    path("teams/<str:abbreviation>/results/<int:season>/", views.season.team_results, name="team_results"),
    path("teams/<str:abbreviation>/", views.site.team_detail),
    path("trades/csv/", views.csv.trades_csv),
    path("trades/", views.site.trades),
    path("schedule/", views.schedule.league_schedule, name="league_schedule"),
    path("schedule/<int:season>/", views.schedule.league_schedule, name="league_schedule"),
    path("standings/", views.season.league_standings, name="league_standings"),
    path("standings/<int:season>/", views.season.league_standings, name="league_standings"),
    path("leaders/", views.season.league_leaders, name="league_leaders"),
    path("leaders/<int:season>/", views.season.league_leaders, name="league_leaders"),
    path("games/<int:game_id>/", views.game.game_page, name="game_page"),
    path("games/<int:game_id>/box/", views.game.game_box_score, name="game_box_score"),
    path("games/<int:game_id>/<str:action>/", views.game.game_action, name="game_action"),
    path("drafts/", views.site.draft_list, name="draft_list"),

    path("special/players/", views.special.player_util),
    path("special/trades/", views.special.trade_util),
    path("special/players/bulk/", views.special.special_bulk_add_players),
    path("special/duplicates/", views.special.duplicate_players_list, name="duplicate_players_list"),
    path("special/duplicates/<int:candidate_id>/", views.special.duplicate_players_detail, name="duplicate_players_detail"),
    path("special/cache/", views.site.cache_admin, name="cache_admin"),
    path("players/trade-block/", views.site.trade_block),
    path("players/unprotected/", views.site.unprotected_players),
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
    path("my/team/", views.my.my_team),
    path("my/api-keys/", views.my.my_api_keys, name="my_api_keys"),
    path("my/<str:list_type>/draft/", views.my.my_draft_prep),
    path("my/wishlist/draft/beta/", views.my.my_wishlist_beta),
    path("", views.site.index),
]
