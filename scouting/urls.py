from django.urls import path
from . import views
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth.views import logout_then_login
from django.urls import path
from .views import picklist_graphs

app_name = 'scouting'

urlpatterns = [

    path('', views.view_index, name="index"),
    path('picklist/', views.view_picklist, name='picklist'),

    path('standsscoutteam/<int:match_number>/<int:team_number>', views.view_match,
         name="stands_scout_match"),  # Changed view_match to view_stands_scout_team
    path('pitscoutteamlist', views.view_pit_scout_team_list, name="pit_scout_teams_list"),
    path('pitscoutteam/<int:team_number>', views.view_pit_scout_team, name="pit_scout_team"),
    path('pitdashboard/', views.view_pit_dashboard, name="pit_dashboard"),
    path('pitdashboard/robot-status/', views.pit_dashboard_robot_status, name="pit_dashboard_robot_status"),
    path('pitdashboard/live-feed/', views.pit_dashboard_live_feed_ingest, name="pit_dashboard_live_feed_ingest"),
    path('pitdashboard/recordings/<int:recording_id>/assign/', views.assign_recording_to_match, name="assign_recording_to_match"),
    path('recording-control/', views.view_recording_control, name="recording_control"),
    path('scouting/teamstatistics/<int:team_number>', views.view_team_statistics, name="team_statistics"),
    path('scouting/teamstatisticslist', views.team_statistics_list, name="team_statistics_list"),
    path('sync/matchdata', views.sync_data, name="sync_match_data"),
    path('sync/pitdata', views.sync_data, name="sync_pit_data"),
    path('update_priority/', views.update_priority, name='update_priority'),

    path('picklist/graphs/', picklist_graphs, name='picklist_graphs')


]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
