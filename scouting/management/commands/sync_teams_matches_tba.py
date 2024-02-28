from django.core.management.base import BaseCommand
from django.core import serializers
import requests
from scouting.models import *
from django.core.management.base import BaseCommand
from django.core.exceptions import ObjectDoesNotExist

class Command(BaseCommand):
    help = 'Update teams and matches from The Blue Alliance API'

    def handle(self, *args, **options):
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
            self.stdout.write(self.style.SUCCESS("Teams and matches updated successfully."))
