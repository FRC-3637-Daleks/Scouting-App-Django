from django.urls import path

from . import views

app_name = 'scouting'

urlpatterns = [
    path('', views.view_index, name="index"),
    path('standsscoutteam/<int:match_number>/<int:team_number>', views.view_match, name="stands_scout_match"),
    path('pitscoutteamlist', views.view_pit_scout_team_list, name="pit_scout_teams_list"),
    path('pitscoutteam/<int:team_number>', views.view_pit_scout_team, name="pit_scout_team"),
    path('scouting/test', views.update_teams_and_matches, name="update_event_teams"),
    path('scouting/teamstatistics/<int:team_number>', views.view_team_statistics, name="view_team_statistics"),
]