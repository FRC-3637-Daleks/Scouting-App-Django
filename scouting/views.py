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
from scouting.models import Alliance, Event
import json

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
    matches = MatchData2025.objects.filter(team=team)

    # Count the number of matches
    match_count = matches.count()
    boolean_stats = {}
    integer_stats = {}
    graphs = {}
    #if match_count > 0:
        #
        # Calculate statistics for boolean fields
        # boolean_fields = ['friendly']
        #
        # for field in boolean_fields:
        #     total = matches.aggregate(total=Sum(field))['total']
        #     if total is not None:
        #         total = int(matches.aggregate(total=Sum(field))['total'])
        #     percent = (total / match_count) * 100 if match_count > 0 else 0
        #     boolean_stats[field] = {
        #         'total': total,
        #         'percent': round(percent, 1)
        #     }

        # Calculate statistics for integer fields
        # integer_fields = []
        #
        # for field in integer_fields:
        #     stats = matches.aggregate(min=Min(field), max=Max(field), avg=Avg(field))
        #     integer_stats[field] = {
        #         'min': round(stats['min'], 1),
        #         'max': round(stats['max'], 1),
        #         'avg': round(stats['avg'], 1)
        #     }
        #     with plt.style.context('dark_background'):
        #         # Create a line graph for this field
        #         plt.figure()
        #         plt.plot(matches.values_list(field, flat=True))
        #         plt.title(field)
        #         plt.xlabel('Match')
        #         plt.ylabel(field)
        #
        #         # Get the match numbers as a range from 1 to the number of matches
        #         match_numbers = range(1, matches.count() + 1)
        #
        #         # Set the x-ticks to be the match numbers
        #         plt.xticks(range(len(match_numbers)), match_numbers)
        #
        #         # Save it to a BytesIO object
        #         buf = BytesIO()
        #         plt.savefig(buf, format='png')
        #         buf.seek(0)
        #
        #         # Encode the bytes as base64 string
        #         string = base64.b64encode(buf.read())
        #         uri = 'data:image/png;base64,' + urllib.parse.quote(string)
        #         integer_stats[field]['graph'] = uri

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
        'graphs': graphs,
        'matches': matches,
    }

    return render(request, 'scouting/statisticsteam.html', context)

@login_required
def update_priority(request):
    team_number = request.POST.get('team_number')
    priority = request.POST.get('priority')
    if not team_number or not priority:
        return JsonResponse({'error': 'Missing parameters'}, status=400)
    try:
        priority = int(priority)
        if priority < 1 or priority > 5:
            return JsonResponse({'error': 'Priority must be between 1 and 5'}, status=400)
        team = Team.objects.get(team_number=team_number)
        event = Event.objects.get(active=True)
        team_ranking, created = TeamRanking.objects.get_or_create(team=team, event=event)
        team_ranking.priority = priority
        team_ranking.save()
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

@login_required()
def view_team_statistics_list(request):
    event = Event.objects.get(active=True)
    teams = event.teams.all()

    context = {
        'teams': teams,
    }

    return render(request, 'scouting/statisticsteamlist.html', context)

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
        team.teamranking = TeamRanking.objects.filter(
            team=team,
            event=event
        ).values(
            'rank', 'opr', 'dpr', 'ccwm', 'priority',
            'l1_coral', 'l2_coral', 'l3_coral', 'l4_coral',
            'net_algae_count', 'wall_algae_count', 'auto_coral_count', 'foul_count'
        ).first()

    return render(request, 'scouting/picklist.html', {
        'teams': teams,
        'current_sort': sort_by,
        'current_direction': direction,
    })

@login_required
def run_alliance_sync(request):
    """
    Triggers the sync_alliances management command and returns a JSON response.
    """
    try:
        call_command('sync_alliances')
        return JsonResponse({'status': 'success'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@login_required
def view_alliances(request):
    """
    Renders a page displaying alliance data.
    Alliances are sorted by:
      1. The numeric value of the first pick's team number,
      2. Then by the declines list (joined as a comma-separated string),
      3. Then by alliance status alphabetically,
      4. Then by backup playoff average (numerically).
    """
    try:
        event = Event.objects.get(active=True)
    except Event.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'No active event found'}, status=404)

    alliances = Alliance.objects.filter(event=event)
    alliance_list = list(alliances)

    def sort_key(alliance):
        try:
            picks = alliance.picks or []
            first_pick = picks[0] if picks else ""
            first_pick_num = int(first_pick[3:]) if first_pick.startswith("frc") else float('inf')
        except Exception:
            first_pick_num = float('inf')
        declines = ", ".join(alliance.declines or [])
        status = alliance.status or ""
        backup_avg = alliance.backup_playoff_average if alliance.backup_playoff_average is not None else float('inf')
        return (first_pick_num, declines, status, backup_avg)

    alliance_list.sort(key=sort_key)

    return render(request, 'scouting/alliances.html', {'alliances': alliance_list})

@login_required
def run_alliance_selection(request):
    """
    Calls the allianceselection management command and returns JSON.
    """
    try:
        call_command('allianceselection')
        return JsonResponse({"status": "success", "message": "Alliance selection command triggered."})
    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=500)


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