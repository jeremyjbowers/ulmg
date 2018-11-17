from django.contrib import admin
from django.urls import include, path

from ulmg import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/v1/player/<int:playerid>/<str:action>/', views.player_action),
    path('teams/<str:abbreviation>/csv/', views.team_csv),
    path('teams/<str:abbreviation>/roster/', views.roster_team_detail),
    path('teams/<str:abbreviation>/protect/', views.protect_team_detail),
    path('teams/<str:abbreviation>/', views.team_detail),
    path('players/search/', views.search),
    path('trade/admin/', views.trade),
    path('', views.index),
]