from django.contrib import admin
from django.urls import include, path

from ulmg import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/v1/player/<int:playerid>/<str:action>/', views.player_action),
    path('api/v1/draft/<str:pickid>/', views.draft_action),
    path('teams/<str:abbreviation>/other/', views.team_other),
    path('teams/<str:abbreviation>/simple/', views.team_simple),
    path('teams/<str:abbreviation>/csv/', views.team_csv),
    path('teams/<str:abbreviation>/roster/', views.roster_team_detail),
    path('teams/<str:abbreviation>/protect/', views.protect_team_detail),
    path('teams/<str:abbreviation>/', views.team_detail),
    path('trades/', views.trades),
    path('players/search/', views.search),
    path('draft/live/<str:year>/<str:season>/<str:draft_type>/', views.live_draft),
    path('', views.index),
]