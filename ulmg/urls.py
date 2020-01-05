from django.contrib import admin
from django.urls import include, path

from ulmg.views import site as site_v
from ulmg.views import adv as adv_v
from ulmg.views import proj as proj_v
from ulmg.views import api as api_v
from ulmg.views import csv as csv_v

urlpatterns = [
    path('proj/', proj_v.index),
    path('proj/players/search/', proj_v.search),
    path('adv/', adv_v.index),
    path('adv/players/search/', site_v.search),
    path('admin/', admin.site.urls),
    path('api/v1/player/', api_v.player_list),
    path('api/v1/draft/live/<int:year>/<str:season>/<str:draft_type>/', api_v.draft_api),
    path('api/v1/player/<int:playerid>/<str:action>/', api_v.player_action),
    path('api/v1/draft/<str:pickid>/', api_v.draft_action),
    path('teams/csv/', csv_v.all_csv),
    path('teams/<str:abbreviation>/csv/', csv_v.team_csv),
    path('teams/<str:abbreviation>/other/', site_v.team_other),
    path('teams/<str:abbreviation>/', site_v.team_detail),
    path('trades/', site_v.trades),
    path('players/util/', site_v.player_util),
    path('players/<int:playerid>/', site_v.player),
    path('players/search/', site_v.search),
    path('draft/live/<int:year>/<str:season>/<str:draft_type>/edit/', site_v.draft_admin),
    path('draft/live/<int:year>/<str:season>/<str:draft_type>/', site_v.draft_watch),
    path('draft/<int:year>/<str:season>/<str:draft_type>/', site_v.draft_recap),
    path('', site_v.index),
]