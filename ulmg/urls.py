from django.contrib import admin
from django.urls import include, path
import nested_admin

from ulmg import views

urlpatterns = [
    path('nested_admin/', include('nested_admin.urls')),
    path('admin/', admin.site.urls),
    path('teams/<str:abbreviation>/', views.team_detail),
    path('players/search/', views.search),
    path('', views.index),
]