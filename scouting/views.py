from django.shortcuts import render
from django.http import HttpResponse
from .models import *
from django.db.models import Q
import requests
from django.forms import formset_factory
from django.core.exceptions import ObjectDoesNotExist
from .forms import *
from django.shortcuts import redirect


def view_index(request):
    event = Event.objects.get(active=True)
    matches_list = Match.objects.filter(event_id=event).order_by('match_number')

    context = {
        'matches': matches_list
    }

    return render(request, 'scouting/index.html', context)



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


def view_match(request, team_number, match_number):
    team = Team.objects.get(team_number=team_number)
    event = Event.objects.get(active=True)
    match = Match.objects.get(match_number=match_number, event_id=event)
    game = event.game

    # Get the MatchFields for this game
    match_fields = list(game.pre_match_fields.all()) + list(game.auton_fields.all()) + list(
        game.teleop_fields.all()) + list(game.endgame_fields.all()) + list(game.post_match_fields.all())
    # print(match_fields)

    # if request.method == 'POST':
    #     print("POST Recieved")
    #     # formset = MatchDataFormSet(request.POST)
    #     formset = MatchDataFormSet(request.POST, form_kwargs={'team': team, 'event': event, 'match': match,
    #                                                           'match_fields': match_fields})
    #     print(formset)
    #     if formset.is_valid():
    #         formset.save()
    #         return redirect('scouting:index')
    #     else:
    #         print(formset.errors)
    # else:
    #     print("NO POST Recieved, Rendering Form")
    #     # Create a MatchData object for each MatchField
    #     for match_field in match_fields:
    #         MatchData.objects.get_or_create(match_field=match_field, team=team, event=event, match=match)
    #
    #     # Convert match_fields list to a QuerySet
    #     match_fields = MatchField.objects.filter(id__in=[mf.id for mf in match_fields])
    #
    #     # Create a formset instance from the MatchData objects
    #     match_data = MatchData.objects.filter(match_field__in=match_fields, team=team, event=event, match=match)
    #     # print(match_data)
    #     # print('Form kwargs:', {'team': team, 'event': event, 'match': match, 'match_fields': match_fields})
    #     formset = MatchDataFormSet(
    #         queryset=MatchData.objects.filter(match_field__in=match_fields, team=team, event=event, match=match),
    #         initial=[
    #             {'id': md.id, 'match_field': md.match_field, 'response_bool': md.response_bool,
    #              'response_int': md.response_int}
    #             for md in match_data
    #         ],
    #         form_kwargs={'team': team, 'event': event, 'match': match, 'match_fields': match_fields},
    #     )
        # print(formset)
    # Check if a PitScoutData object already exists for this team and event
    match_data, created = MatchData2024.objects.get_or_create(team=team, match=match)

    if request.method == 'POST':
        # If the form has been submitted, create a form instance with the POST data and the existing PitScoutData object
        form = MatchDataForm2024(request.POST, instance=match_data)

        # Validate the form
        if form.is_valid():
            # Save the form data to the database
            form.save()

            # Redirect to the same page (or wherever you want to redirect to)
            return redirect('scouting:index')
    else:
        # If the form has not been submitted, create a form instance from the PitScoutData object
        form = MatchDataForm2024(instance=match_data)

    context = {
        'form': form,
        'match': match,
        'team': team,
    }

    return render(request, 'scouting/match.html', context)


def update_teams_and_matches(request):
    try:
        api_key = TbaApiKey.objects.get(active=True).api_key
    except ObjectDoesNotExist:
        print("Active API key not found.")
        return

    headers = {"X-TBA-Auth-Key": api_key}

    event_key = Event.objects.get(active=True).tba_event_key

    # Get teams
    response = requests.get("https://www.thebluealliance.com/api/v3/event/" + event_key + "/teams/simple",
                            headers=headers)
    teams = response.json()

    event = Event.objects.get(active=True)

    for team in teams:
        # Create or update the Team object
        team_obj, created = Team.objects.update_or_create(
            team_number=team['team_number'],
            defaults={'team_name': team['nickname']}
        )

        # Add the team to the event
        event.teams.add(team_obj)

    # Save the event
    event.save()

    # # Get matches
    response = requests.get("https://www.thebluealliance.com/api/v3/event/" + event_key + "/matches/simple",
                            headers=headers)
    matches = response.json()

    for match in matches:
        # Only process qualification matches
        if match['comp_level'] == 'qm':
            # Your existing code to create or update Match objects
            Match.objects.update_or_create(
                match_number=match['match_number'],
                event_id=Event.objects.get(active=True),
                defaults={
                    'team_red_1': Team.objects.get_or_create(
                        team_number=match['alliances']['red']['team_keys'][0][3:] if
                        match['alliances']['red']['team_keys'][0] else 9999)[0],
                    'team_red_2': Team.objects.get_or_create(
                        team_number=match['alliances']['red']['team_keys'][1][3:] if
                        match['alliances']['red']['team_keys'][1] else 9999)[0],
                    'team_red_3': Team.objects.get_or_create(
                        team_number=match['alliances']['red']['team_keys'][2][3:] if
                        match['alliances']['red']['team_keys'][2] else 9999)[0],
                    'team_blue_1': Team.objects.get_or_create(
                        team_number=match['alliances']['blue']['team_keys'][0][3:] if
                        match['alliances']['blue']['team_keys'][0] else 9999)[0],
                    'team_blue_2': Team.objects.get_or_create(
                        team_number=match['alliances']['blue']['team_keys'][1][3:] if
                        match['alliances']['blue']['team_keys'][1] else 9999)[0],
                    'team_blue_3': Team.objects.get_or_create(
                        team_number=match['alliances']['blue']['team_keys'][2][3:] if
                        match['alliances']['blue']['team_keys'][2] else 9999)[0]
                }
            )
    return HttpResponse("Teams updated, check the database in Django admin!")
