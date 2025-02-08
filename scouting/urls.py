from django.urls import path

from . import views
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth.views import logout_then_login
app_name = 'scouting'

urlpatterns = [
    path('', views.view_index, name="index"),
    path('standsscoutteam/<int:match_number>/<int:team_number>', views.view_match, name="stands_scout_match"),
    path('pitscoutteamlist', views.view_pit_scout_team_list, name="pit_scout_teams_list"),
    path('pitscoutteam/<int:team_number>', views.view_pit_scout_team, name="pit_scout_team"),
    path('scouting/teamstatistics/<int:team_number>', views.view_team_statistics, name="team_statistics"),
    path('scouting/teamstatisticslist', views.view_team_statistics_list, name="team_statistics_list"),
    path('sync/matchdata', views.sync_data, name="sync_data"),
    path('sync/pitdata', views.sync_data, name="sync_data"),
    path('picklist/', views.view_picklist, name='picklist'),


]