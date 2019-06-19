from django.contrib import admin
from django.urls import include, path

from ulmg import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/v1/player/', views.player_list),
    path('api/v1/draft/live/<int:year>/<str:season>/<str:draft_type>/', views.live_draft_api),
    path('api/v1/player/<int:playerid>/<str:action>/', views.player_action),
    path('api/v1/draft/<str:pickid>/', views.draft_action),
    path('teams/csv/', views.all_csv),
    path('teams/<str:abbreviation>/live/', views.team_livestat_detail),
    path('teams/<str:abbreviation>/other/', views.team_other),
    path('teams/<str:abbreviation>/simple/', views.team_simple),
    path('teams/<str:abbreviation>/csv/', views.team_csv),
    path('teams/<str:abbreviation>/roster/', views.roster_team_detail),
    path('teams/<str:abbreviation>/protect/', views.protect_team_detail),
    path('teams/<str:abbreviation>/', views.team_detail),
    path('trades/', views.trades),
    path('players/<int:playerid>/', views.player),
    path('players/interesting/', views.interesting),
    path('players/search/', views.search),
    path('players/available/', views.available_livestat),
    path('players/unprotected/', views.unprotected),
    path('draft/live/<int:year>/<str:season>/<str:draft_type>/edit/', views.live_draft_admin),
    path('draft/live/<int:year>/<str:season>/<str:draft_type>/', views.live_draft_watch),
    path('', views.index),
]