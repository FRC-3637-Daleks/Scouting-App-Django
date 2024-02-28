from django.shortcuts import render
from django.http import HttpResponse
from .models import *
from django.db.models import Q
import requests
from django.forms import formset_factory
from django.core.exceptions import ObjectDoesNotExist
from .forms import *
from django.shortcuts import redirect
from django.db.models import Count, Avg, Min, Max, Sum
from django.shortcuts import get_object_or_404
from django.forms.models import model_to_dict
from django.core import serializers
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required, permission_required
from rest_framework.authentication import TokenAuthentication
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import IsAuthenticated


@login_required()
def view_index(request):
    event = Event.objects.get(active=True)
    matches_list = Match.objects.filter(event_id=event).order_by('match_number')

    context = {
        'matches': matches_list
    }

    return render(request, 'scouting/index.html', context)


@login_required()
@permission_required('scouting.pit_scout_team', raise_exception=True)
def view_pit_scout_team_list(request):
    event = Event.objects.get(active=True)
    event_teams = event.teams.all().order_by('team_number')
    for team in event_teams:
        PitScoutData.objects.update_or_create(
            team=team,
            event=event,
        )

    pit_scout_reports = PitScoutData.objects.filter(event=event).order_by('team__team_number')

    context = {
        'pit_scout_reports': pit_scout_reports,
        'current_user': request.user,
    }

    return render(request, 'scouting/pitscoutteamlist.html', context)


@login_required()
@permission_required('scouting.pit_scout_team', raise_exception=True)
def view_pit_scout_team(request, team_number):
    team = Team.objects.get(team_number=team_number)
    event = Event.objects.get(active=True)
    pit_scout_data, created = PitScoutData.objects.get_or_create(team=team, event=event)

    if request.method == 'POST':
        # If the form has been submitted, create a form instance with the POST data and the existing PitScoutData object
        form = PitScoutDataForm(request.POST, instance=pit_scout_data)

        # Validate the form
        if form.is_valid():
            # Save the form data to the database
            form.save()

            # Redirect to the same page (or wherever you want to redirect to)
            return redirect('scouting:pit_scout_teams_list')
    else:
        # If the form has not been submitted, create a form instance from the PitScoutData object
        form = PitScoutDataForm(instance=pit_scout_data)

    context = {
        'form': form,
        'pit_scout_data': pit_scout_data,
    }

    return render(request, 'scouting/pitscoutteam.html', context)


@login_required()
@permission_required('scouting.stands_scout_team', raise_exception=True)
def view_match(request, team_number, match_number):
    team = Team.objects.get(team_number=team_number)
    event = Event.objects.get(active=True)
    match = Match.objects.get(match_number=match_number, event_id=event)

    # Check if a PitScoutData object already exists for this team and event
    match_data, created = MatchData2024.objects.get_or_create(team=team, match=match)

    if request.method == 'POST':
        # If the form has been submitted, create a form instance with the POST data and the existing PitScoutData object
        form = MatchData2024Form(request.POST, instance=match_data)

        # Validate the form
        if form.is_valid():
            # Save the form data to the database
            form.save()

            # Redirect to the same page (or wherever you want to redirect to)
            return redirect('scouting:index')
    else:
        # If the form has not been submitted, create a form instance from the PitScoutData object
        form = MatchData2024Form(instance=match_data)
        # print(form)

    context = {
        'form': form,
        'match': match,
        'team': team,
    }

    return render(request, 'scouting/match.html', context)


@login_required()
def view_team_statistics(request, team_number):
    team = get_object_or_404(Team, team_number=team_number)
    matches = MatchData2024.objects.filter(team=team)

    # Count the number of matches
    match_count = matches.count()

    # Calculate statistics for boolean fields
    boolean_fields = ['arrived_on_field_on_time', 'start_with_note', 'dead_on_arrival', 'left_community_zone', 'moved', 'a_stopped', 'e_stopped', 'communication_lost', 'shoots_from_subwoofer_to_speaker', 'shoots_from_podium_to_speaker', 'shoots_from_free_space_to_speaker', 'climbed_solo', 'climbed_with_another_robot', 'scored_high_notes']
    boolean_stats = {}
    for field in boolean_fields:
        total = matches.aggregate(total=Sum(field))['total']
        if total is not None:
            total = int(matches.aggregate(total=Sum(field))['total'])
        percent = (total / match_count) * 100 if match_count > 0 else 0
        boolean_stats[field] = {
            'total': total,
            'percent': round(percent, 1)
        }

    # Calculate statistics for integer fields
    integer_fields = ['amp_notes_scored', 'speaker_notes_scored', 'notes_picked_up_from_wing', 'notes_picked_up_from_center', 'time_to_centerline_note', 'notes_scored_from_subwoofer', 'notes_scored_from_elesewhere', 'speaker_notes_missed', 'defense_scale', 'notes_picked_up_from_floor', 'notes_picked_up_from_player_station', 'notes_dropped', 'notes_scored_in_trap']
    integer_stats = {}
    for field in integer_fields:
        stats = matches.aggregate(min=Min(field), max=Max(field), avg=Avg(field))
        integer_stats[field] = {
            'min': round(stats['min'], 1),
            'max': round(stats['max'], 1),
            'avg': round(stats['avg'], 1)
        }

    # Include pit scouting information
    pit_scout_data = PitScoutData.objects.get(team=team, event=Event.objects.get(active=True))

    if pit_scout_data is not None:
        pit_scout_data_dict = model_to_dict(pit_scout_data)
        pit_scout_data_dict.pop('team')
        pit_scout_data_dict.pop('id')
        pit_scout_data_dict.pop('event')
        if pit_scout_data.assigned_scout is not None:
            pit_scout_data_dict['assigned_scout'] = pit_scout_data.assigned_scout.first_name + " " + pit_scout_data.assigned_scout.last_name
        else:
            pit_scout_data_dict['assigned_scout'] = "No scout assigned"
    else:
        pit_scout_data_dict = {}

    context = {
        'team': team,
        'match_count': match_count,
        'boolean_stats': boolean_stats,
        'integer_stats': integer_stats,
        'pit_scout_data': pit_scout_data_dict,
    }

    return render(request, 'scouting/statisticsteam.html', context)


@login_required()
def view_team_statistics_list(request):
    event = Event.objects.get(active=True)
    teams = event.teams.all()

    context = {
        'teams': teams,
    }

    return render(request, 'scouting/statisticsteamlist.html', context)


@api_view(['POST'])  # Specify the allowed HTTP methods
@authentication_classes([TokenAuthentication])  # Use TokenAuthentication
@permission_classes([IsAuthenticated])  # Require authenticated users
def sync_data(request):
    if request.method == 'POST':
        # Deserialize the data back into Django objects
        for obj in serializers.deserialize('json', request.body):
            # If the object already exists, update it. Otherwise, create a new one.
            obj.save()

        return JsonResponse({'status': 'success'})
    else:
        return JsonResponse({'status': 'error'}, status=400)