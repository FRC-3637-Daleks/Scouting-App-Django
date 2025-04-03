from .forms import *
from django.shortcuts import redirect
from django.forms.models import model_to_dict
from django.core import serializers
from django.contrib.auth.decorators import login_required, permission_required
from rest_framework.authentication import TokenAuthentication
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import IsAuthenticated
from .models import Team, Event, PitScoutData
from .forms import PitScoutDataForm
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.core.management import call_command
from django.contrib.auth.decorators import login_required
import json
from django.shortcuts import render
from .models import TeamRanking
from django.db.models import F
from django.db.models import OuterRef, Subquery, Value, FloatField, IntegerField
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
        form = PitScoutDataForm(request.POST, request.FILES, instance=pit_scout_data)
        if form.is_valid():
            form.save()
            return redirect('scouting:pit_scout_teams_list')
    else:
        form = PitScoutDataForm(instance=pit_scout_data)

    context = {
        'form': form,
        'pit_scout_data': pit_scout_data,
        'media_url': settings.MEDIA_URL,  # Added to help templates build image URLs
    }

    return render(request, 'scouting/pitscoutteam.html', context)
@login_required()
@permission_required('scouting.stands_scout_team', raise_exception=True)
def view_match(request, team_number, match_number):
    team = Team.objects.get(team_number=team_number)
    event = Event.objects.get(active=True)
    match = Match.objects.get(match_number=match_number, event_id=event)

    # Check if a PitScoutData object already exists for this team and event
    match_data, created = MatchData2025.objects.get_or_create(team=team, match=match)

    if request.method == 'POST':
        # If the form has been submitted, create a form instance with the POST data and the existing PitScoutData object
        form = MatchData2025Form(request.POST, instance=match_data)
        print("Form POSTed")

        # Validate the form
        if form.is_valid():
            # Save the form data to the database
            form.save()

            # Redirect to the same page (or wherever you want to redirect to)
            return redirect('scouting:index')
    else:
        # If the form has not been submitted, create a form instance from the PitScoutData object
        form = MatchData2025Form(instance=match_data)

    context = {
        'form': form,
        'match': match,
        'team': team,
    }

    return render(request, 'scouting/match.html', context)


@login_required()
def view_team_statistics(request, team_number):
    team = get_object_or_404(Team, team_number=team_number)

    # Get active event
    active_event = Event.objects.filter(active=True).first()

    # Fetch match data for the team
    match_data = MatchData2025.objects.filter(team=team)

    # Count the number of matches played
    match_count = match_data.count()

    # Get pit scouting data for the active event
    pit_scout_data = PitScoutData.objects.filter(team=team, event=active_event).first()

    if pit_scout_data:
        pit_scout_data_dict = model_to_dict(pit_scout_data)
        # Remove unnecessary fields
        pit_scout_data_dict.pop('id', None)
        pit_scout_data_dict.pop('team', None)
        pit_scout_data_dict.pop('event', None)

        # Format assigned scout name
        if pit_scout_data.assigned_scout:
            pit_scout_data_dict[
                'assigned_scout'] = f"{pit_scout_data.assigned_scout.first_name} {pit_scout_data.assigned_scout.last_name}"
        else:
            pit_scout_data_dict['assigned_scout'] = "No scout assigned"

        # Gather images
        pit_scout_images = [
            pit_scout_data.auton_picture_1,
            pit_scout_data.auton_picture_2,
            pit_scout_data.auton_picture_3,
            pit_scout_data.robot_picture_1,
            pit_scout_data.robot_picture_2,
        ]
        # Filter out any `None` values
        pit_scout_images = [img for img in pit_scout_images if img]
    else:
        pit_scout_data_dict = {}
        pit_scout_images = []

    # Get team ranking for the active event
    team_ranking = TeamRanking.objects.filter(team=team, event=active_event).first()

    context = {
        'team': team,
        'match_count': match_count,
        'pit_scout_data': pit_scout_data_dict,
        'pit_scout_images': pit_scout_images,
        'match_data': match_data,
        'team_ranking': team_ranking,
    }

    return render(request, 'scouting/statisticsteam.html', context)

@login_required
def update_priority(request):
    if request.method == "POST":
        try:
            team_number = request.POST.get("team_number")
            priority_value = request.POST.get("priority")

            if not team_number or not priority_value:
                return JsonResponse({"success": False, "error": "Missing team_number or priority"})

            priority_value = int(priority_value)  # Convert to integer

            if priority_value < 1 or priority_value > 5:
                return JsonResponse({"success": False, "error": "Priority must be between 1 and 5"})

            team = get_object_or_404(Team, team_number=team_number)
            event = get_object_or_404(Event, active=True)

            team_ranking, _ = TeamRanking.objects.get_or_create(team=team, event=event)
            team_ranking.priority = priority_value
            team_ranking.save()

            return JsonResponse({"success": True, "priority": priority_value})

        except ValueError:
            return JsonResponse({"success": False, "error": "Invalid priority value"})
        except Exception as e:
            return JsonResponse({"success": False, "error": str(e)})

    return JsonResponse({"success": False, "error": "Invalid request"})

@login_required()
def team_statistics_list(request):
    # Get sorting parameters from the request
    order_by = request.GET.get('order_by', 'team_number')  # Default to team_number
    direction = request.GET.get('direction', 'asc')

    # Validate order direction
    if direction not in ['asc', 'desc']:
        direction = 'asc'

    # Adjust ordering dynamically
    ordering = order_by if direction == 'asc' else f"-{order_by}"

    # Fetch and order teams
    teams = Team.objects.all().order_by(ordering)

    context = {
        'teams': teams,
        'order_by': order_by,
        'direction': direction,
    }
    return render(request, 'scouting/team_statistics_list.html', context)

from django.db.models import OuterRef, Subquery, Value

def view_picklist(request):
    event = Event.objects.get(active=True)
    sort_by = request.GET.get('sort', 'team_number')
    direction = request.GET.get('direction', 'asc')

    teams = event.teams.all().select_related().prefetch_related('teamranking_set')

    if sort_by in ['rank', 'opr', 'dpr', 'ccwm', 'priority',
                   'l1_coral', 'l2_coral', 'l3_coral', 'l4_coral',
                   'net_algae_count', 'wall_algae_count', 'auto_coral_count', 'foul_count']:
        order_field = f'teamranking__{sort_by}'
        if direction == 'desc':
            order_field = f'-{order_field}'
        teams = teams.order_by(order_field)
    else:
        teams = teams.order_by(f'{"-" if direction == "desc" else ""}team_number')

    for team in teams:
        team.teamranking, _ = TeamRanking.objects.get_or_create(
            team=team,
            event=event,
            defaults={'rank': 0}  # Set a default rank
        )

    return render(request, 'scouting/picklist.html', {
        'teams': teams,
        'current_sort': sort_by,
        'current_direction': direction,
    })
def picklist_graphs(request):
    currentevent = Event.objects.get(active=True)
    teams_qs = currentevent.teams.all()
    teams_data = []

    for team in teams_qs:
        ranking, created = TeamRanking.objects.get_or_create(
            team=team,
            event=currentevent,
            defaults={'rank': 0}
        )
        teams_data.append({
            'team_number': team.team_number,
            'opr': ranking.opr or 0,
            'dpr': ranking.dpr or 0,
            'rank': ranking.rank or 0,
            'l1_coral': ranking.l1_coral or 0,
            'l2_coral': ranking.l2_coral or 0,
            'l3_coral': ranking.l3_coral or 0,
            'l4_coral': ranking.l4_coral or 0,
            'net_algae': ranking.net_algae_count or 0,
            'wall_algae': ranking.wall_algae_count or 0,
            'barge_points': ranking.end_game_barge_points or 0,
            'auto_coral': ranking.auto_coral_count or 0,
        })

    # Sort the teams_data by rank
    teams_data.sort(key=lambda x: x['rank'], reverse=True)

    # Now prepare lists for the graph context.
    context = {
        "teams": [d['team_number'] for d in teams_data],
        "opr_values": [round(d['opr'], 2) for d in teams_data],
        "dpr_values": [round(d['dpr'], 2) for d in teams_data],
        "rank_values": [d['rank'] for d in teams_data],
        "l1_coral_values": [d['l1_coral'] for d in teams_data],
        "l2_coral_values": [d['l2_coral'] for d in teams_data],
        "l3_coral_values": [d['l3_coral'] for d in teams_data],
        "l4_coral_values": [d['l4_coral'] for d in teams_data],
        "net_algae_values": [d['net_algae'] for d in teams_data],
        "wall_algae_values": [d['wall_algae'] for d in teams_data],
        "barge_points_values": [d['barge_points'] for d in teams_data],
        "auto_coral_values": [d['auto_coral'] for d in teams_data],
    }
    return render(request, "scouting/picklist_graphs.html", context)


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