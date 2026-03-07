from .forms import *
from django.shortcuts import redirect
from django.forms.models import model_to_dict
from django.core import serializers
from django.conf import settings
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
from .models import TeamRanking, Match, NexusApiKey
from django.db.models import F
from django.db.models import OuterRef, Subquery, Value, FloatField, IntegerField
from pathlib import Path
from PIL import Image
import requests
import re
from datetime import datetime, timezone as dt_timezone
from zoneinfo import ZoneInfo


def _get_standscout_compressed_url(image_field, max_width=900, quality=65):
    """
    Build and cache a compressed JPEG copy for stand scout screens.
    Returns a media URL or None when source image does not exist.
    """
    if not image_field:
        return None

    try:
        source_path = Path(image_field.path)
    except Exception:
        return None

    if not source_path.exists():
        return None

    cache_dir = Path(settings.MEDIA_ROOT) / "cache" / "standscout"
    cache_dir.mkdir(parents=True, exist_ok=True)

    stamp = int(source_path.stat().st_mtime)
    cache_name = f"{source_path.stem}_{stamp}.jpg"
    cache_path = cache_dir / cache_name

    if not cache_path.exists():
        with Image.open(source_path) as img:
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            img.thumbnail((max_width, max_width), Image.Resampling.LANCZOS)
            img.save(cache_path, format="JPEG", quality=quality, optimize=True, progressive=True)

    return f"{settings.MEDIA_URL}cache/standscout/{cache_name}"


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
    pit_scout_data = PitScoutData.objects.filter(team=team, event=event).first()

    # Check if a PitScoutData object already exists for this team and event
    match_data, created = MatchData2026.objects.get_or_create(team=team, match=match)

    if request.method == 'POST':
        # If the form has been submitted, create a form instance with the POST data and the existing PitScoutData object
        form = MatchData2026Form(request.POST, instance=match_data)
        print("Form POSTed")

        # Validate the form
        if form.is_valid():
            # Save the form data to the database
            form.save()

            # Redirect to the same page (or wherever you want to redirect to)
            return redirect('scouting:index')
    else:
        # If the form has not been submitted, create a form instance from the PitScoutData object
        form = MatchData2026Form(instance=match_data)

    robot_photo_urls = []
    if pit_scout_data:
        robot_photos = [pit_scout_data.robot_picture_1, pit_scout_data.robot_picture_2]
        robot_photo_urls = [
            _get_standscout_compressed_url(photo)
            for photo in robot_photos
            if photo
        ]
        robot_photo_urls = [url for url in robot_photo_urls if url]

    context = {
        'form': form,
        'match': match,
        'team': team,
        'robot_photo_urls': robot_photo_urls,
    }

    return render(request, 'scouting/match.html', context)


@login_required()
def view_team_statistics(request, team_number):
    team = get_object_or_404(Team, team_number=team_number)

    # Get active event
    active_event = Event.objects.filter(active=True).first()

    # Fetch match data for the team
    match_data = MatchData2026.objects.filter(team=team)

    # Count the number of matches played
    match_count = match_data.count()

    # Get pit scouting data for the active event
    pit_scout_data = PitScoutData.objects.filter(team=team, event=active_event).first()

    if pit_scout_data:
        pit_scout_data_dict = model_to_dict(pit_scout_data)
        image_fields = {
            'auton_picture_1',
            'auton_picture_2',
            'auton_picture_3',
            'robot_picture_1',
            'robot_picture_2',
        }
        # Remove non-display fields from table rows.
        for field_name in ['id', 'team', 'event', *image_fields]:
            pit_scout_data_dict.pop(field_name, None)

        # Format assigned scout name
        if pit_scout_data.assigned_scout:
            pit_scout_data_dict['assigned_scout'] = (
                f"{pit_scout_data.assigned_scout.first_name} "
                f"{pit_scout_data.assigned_scout.last_name}"
            ).strip()
        else:
            pit_scout_data_dict['assigned_scout'] = "No scout assigned"

        # Build display rows using field verbose names instead of raw db keys.
        pit_scout_data_rows = []
        for field_name, value in pit_scout_data_dict.items():
            if field_name == 'frc_nexus_url':
                # Show Nexus link via the pit_location row instead of raw URL row.
                continue

            label = pit_scout_data._meta.get_field(field_name).verbose_name
            if isinstance(value, bool):
                value = "Yes" if value else "No"

            row = {
                'label': str(label).title(),
                'value': value,
            }

            if field_name == 'pit_location' and value and pit_scout_data.frc_nexus_url:
                row['link_url'] = pit_scout_data.frc_nexus_url

            pit_scout_data_rows.append(row)

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
        pit_scout_data_rows = []
        pit_scout_images = []

    # Get team ranking for the active event
    team_ranking = TeamRanking.objects.filter(team=team, event=active_event).first()

    context = {
        'team': team,
        'match_count': match_count,
        'pit_scout_data': pit_scout_data_rows,
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

            priority_value = float(priority_value)  # Convert to integer

            if priority_value < 1 or priority_value > 10:
                return JsonResponse({"success": False, "error": "Priority must be between 1 and 10"})

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

    teams = list(event.teams.all())

    sortable_fields = [
        'rank',
        'opr',
        'dpr',
        'ccwm',
        'priority',
        'auto_tower_points',
        'total_auto_points',
        'total_teleop_points',
        'endgame_tower_points',
        'total_tower_points',
        'hub_total_fuel_count',
        'hub_teleop_fuel_count',
        'hub_endgame_fuel_count',
        'minor_foul_count',
        'major_foul_count',
        'foul_points',
    ]

    for team in teams:
        team.ranking, _ = TeamRanking.objects.get_or_create(
            team=team,
            event=event,
            defaults={'rank': 0}  # Set a default rank
        )

    reverse = direction == 'desc'
    if sort_by in sortable_fields:
        teams.sort(key=lambda t: getattr(t.ranking, sort_by) or 0, reverse=reverse)
    elif sort_by == 'team_number':
        teams.sort(key=lambda t: t.team_number, reverse=reverse)
    else:
        teams.sort(key=lambda t: t.team_number)

    return render(request, 'scouting/picklist.html', {
        'teams': teams,
        'event': event,
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
            'ccwm': ranking.ccwm or 0,
            'rank': ranking.rank or 0,
            'auto_tower_points': ranking.auto_tower_points or 0,
            'total_auto_points': ranking.total_auto_points or 0,
            'total_teleop_points': ranking.total_teleop_points or 0,
            'endgame_tower_points': ranking.endgame_tower_points or 0,
            'total_tower_points': ranking.total_tower_points or 0,
            'hub_auto_fuel_count': ranking.hub_auto_fuel_count or 0,
            'hub_teleop_fuel_count': ranking.hub_teleop_fuel_count or 0,
            'hub_endgame_fuel_count': ranking.hub_endgame_fuel_count or 0,
            'hub_total_fuel_count': ranking.hub_total_fuel_count or 0,
            'minor_foul_count': ranking.minor_foul_count or 0,
            'major_foul_count': ranking.major_foul_count or 0,
            'foul_points': ranking.foul_points or 0,
        })

    # Sort the teams_data by rank
    teams_data.sort(key=lambda x: x['rank'], reverse=True)

    # Now prepare lists for the graph context.
    context = {
        "teams": [d['team_number'] for d in teams_data],
        "opr_values": [round(d['opr'], 2) for d in teams_data],
        "dpr_values": [round(d['dpr'], 2) for d in teams_data],
        "ccwm_values": [round(d['ccwm'], 2) for d in teams_data],
        "rank_values": [d['rank'] for d in teams_data],
        "auto_tower_points_values": [round(d['auto_tower_points'], 2) for d in teams_data],
        "total_auto_points_values": [round(d['total_auto_points'], 2) for d in teams_data],
        "total_teleop_points_values": [round(d['total_teleop_points'], 2) for d in teams_data],
        "endgame_tower_points_values": [round(d['endgame_tower_points'], 2) for d in teams_data],
        "total_tower_points_values": [round(d['total_tower_points'], 2) for d in teams_data],
        "hub_auto_fuel_count_values": [round(d['hub_auto_fuel_count'], 2) for d in teams_data],
        "hub_teleop_fuel_count_values": [round(d['hub_teleop_fuel_count'], 2) for d in teams_data],
        "hub_endgame_fuel_count_values": [round(d['hub_endgame_fuel_count'], 2) for d in teams_data],
        "hub_total_fuel_count_values": [round(d['hub_total_fuel_count'], 2) for d in teams_data],
        "minor_foul_count_values": [round(d['minor_foul_count'], 2) for d in teams_data],
        "major_foul_count_values": [round(d['major_foul_count'], 2) for d in teams_data],
        "foul_points_values": [round(d['foul_points'], 2) for d in teams_data],
    }
    return render(request, "scouting/picklist_graphs.html", context)


@login_required()
def view_pit_dashboard(request):
    event = Event.objects.get(active=True)

    # Show Team 3637 schedule in the same table format as the match schedule.
    team_number = 3637
    team_matches = Match.objects.filter(
        event_id=event
    ).filter(
        team_red_1__team_number=team_number
    ) | Match.objects.filter(
        event_id=event, team_red_2__team_number=team_number
    ) | Match.objects.filter(
        event_id=event, team_red_3__team_number=team_number
    ) | Match.objects.filter(
        event_id=event, team_blue_1__team_number=team_number
    ) | Match.objects.filter(
        event_id=event, team_blue_2__team_number=team_number
    ) | Match.objects.filter(
        event_id=event, team_blue_3__team_number=team_number
    )
    team_matches = team_matches.order_by("match_number").distinct()

    nexus_status = {}
    announcements = []
    parts_requests = []
    now_queuing = None
    nexus_error = None
    current_qual_match_num = None
    queue_time_by_match = {}
    display_tz = ZoneInfo("America/New_York")

    try:
        nexus_key = NexusApiKey.objects.get(active=True).api_key
        response = requests.get(
            f"https://frc.nexus/api/v1/event/{event.tba_event_key}",
            headers={"Nexus-Api-Key": nexus_key},
            timeout=10,
        )
        response.raise_for_status()
        nexus_status = response.json()

        now_queuing = nexus_status.get("nowQueuing")
        announcements = nexus_status.get("announcements") or []
        parts_requests = nexus_status.get("partsRequests") or []

        if isinstance(now_queuing, str):
            match = re.search(r"Qualification\s+(\d+)", now_queuing, flags=re.IGNORECASE)
            if match:
                current_qual_match_num = int(match.group(1))

        # Pull estimated queue time for qualification matches from Nexus payload.
        for nexus_match in nexus_status.get("matches", []):
            if not isinstance(nexus_match, dict):
                continue
            label = nexus_match.get("label") or ""
            match = re.search(r"^Qualification\s+(\d+)", label, flags=re.IGNORECASE)
            if not match:
                continue

            match_number = int(match.group(1))
            queue_time_ms = (nexus_match.get("times") or {}).get("estimatedQueueTime")
            if not queue_time_ms:
                continue

            try:
                local_dt = datetime.fromtimestamp(queue_time_ms / 1000, tz=dt_timezone.utc).astimezone(display_tz)
                queue_time_by_match[match_number] = local_dt.strftime("%I:%M %p").lstrip("0")
            except Exception:
                continue
    except NexusApiKey.DoesNotExist:
        nexus_error = "No active Nexus API key configured."
    except requests.RequestException:
        nexus_error = "Unable to load live event status from FRC Nexus."
    except ValueError:
        nexus_error = "FRC Nexus returned invalid data."

    # Show a rolling window: 3 matches before now-queuing plus current/upcoming.
    if current_qual_match_num:
        team_matches = team_matches.filter(match_number__gte=max(1, current_qual_match_num - 3))

    match_rows = [{"match": m, "queue_time": queue_time_by_match.get(m.match_number, "-")} for m in team_matches]

    context = {
        "event": event,
        "team_number": team_number,
        "match_rows": match_rows,
        "now_queuing": now_queuing,
        "announcements": announcements,
        "parts_requests": parts_requests,
        "nexus_error": nexus_error,
    }
    return render(request, "scouting/pit_dashboard.html", context)


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
