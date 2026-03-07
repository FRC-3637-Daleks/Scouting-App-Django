from django.core.management.base import BaseCommand
import requests
from cachecontrol import CacheControl
from scouting.models import *
from django.core.exceptions import ObjectDoesNotExist

class Command(BaseCommand):
    help = 'Update team rank and COPRs (Component OPRs) from The Blue Alliance API'

    CATEGORY_TO_FIELD = {
        # 2026 top-level score breakdown components
        'autoTowerPoints': 'auto_tower_points',
        'totalAutoPoints': 'total_auto_points',
        'totalTeleopPoints': 'total_teleop_points',
        'endGameTowerPoints': 'endgame_tower_points',
        'totalTowerPoints': 'total_tower_points',
        'energizedAchieved': 'energized_achieved',
        'superchargedAchieved': 'supercharged_achieved',
        'traversalAchieved': 'traversal_achieved',
        'minorFoulCount': 'minor_foul_count',
        'majorFoulCount': 'major_foul_count',
        'foulPoints': 'foul_points',
        'g206Penalty': 'g206_penalty',

        # 2026 HubScore nested fields (COPR key format TBD by TBA backend)
        'Hub Auto Fuel Count': 'hub_auto_fuel_count',
        'Hub Teleop Fuel Count': 'hub_teleop_fuel_count',
        'Hub Endgame Fuel Count': 'hub_endgame_fuel_count',
        'Hub Total Fuel Count': 'hub_total_fuel_count',
        'Hub Transition Fuel Count': 'hub_transition_fuel_count',
        'Hub Shift 1 Fuel Count': 'hub_shift_1_fuel_count',
        'Hub Shift 2 Fuel Count': 'hub_shift_2_fuel_count',
        'Hub Shift 3 Fuel Count': 'hub_shift_3_fuel_count',
        'Hub Shift 4 Fuel Count': 'hub_shift_4_fuel_count',
    }

    def handle(self, *args, **options):
        # Get active API key
        try:
            api_key = TbaApiKey.objects.get(active=True).api_key
        except ObjectDoesNotExist:
            self.stdout.write(self.style.ERROR("Active API key not found."))
            return

        # Set up a requests session with caching
        session = CacheControl(requests.Session())
        headers = {'X-TBA-Auth-Key': api_key}

        # Get active event
        try:
            event = Event.objects.get(active=True)
        except Event.DoesNotExist:
            self.stdout.write(self.style.ERROR("No active event found."))
            return

        # Build the COPR endpoint URL and fetch data
        rankings_url = f'https://www.thebluealliance.com/api/v3/event/{event.tba_event_key}/rankings'
        url = f'https://www.thebluealliance.com/api/v3/event/{event.tba_event_key}/coprs'
        rankings_response = session.get(rankings_url, headers=headers)
        if rankings_response.status_code == 200:
            rankings_data = rankings_response.json() or {}
            for rank_data in rankings_data.get("rankings", []):
                team_key = rank_data.get("team_key")
                if not team_key or not str(team_key).startswith("frc"):
                    continue
                team_number = team_key[3:]
                try:
                    team = Team.objects.get(team_number=team_number)
                except Team.DoesNotExist:
                    continue

                ranking, _ = TeamRanking.objects.get_or_create(
                    team=team,
                    event=event,
                    defaults={'rank': 0}
                )
                ranking.rank = rank_data.get("rank", ranking.rank or 0)
                ranking.save(update_fields=["rank"])

        response = session.get(url, headers=headers)
        if response.status_code != 200:
            self.stdout.write(self.style.ERROR(f"Failed to fetch data from TBA: {response.status_code}"))
            return

        coprs_data = response.json()
        if not coprs_data:
            self.stdout.write(self.style.ERROR("No COPR data available"))
            return
#        if response.status_code == 200:
 #           data = response.json()
 #           print(data)  # Print entire JSON response to check other copr components

        # Process each category and save both mapped fields and raw cOPR values.
        for category, component_values in coprs_data.items():
            if not isinstance(component_values, dict):
                continue

            for team_key, value in component_values.items():
                if not team_key.startswith("frc"):
                    continue

                team_number = team_key[3:]
                try:
                    team = Team.objects.get(team_number=team_number)
                except Team.DoesNotExist:
                    self.stdout.write(self.style.WARNING(f"Team {team_number} not found in database"))
                    continue

                ranking, _ = TeamRanking.objects.get_or_create(
                    team=team,
                    event=event,
                    defaults={'rank': 0}
                )

                numeric_value = round(float(value), 2)
                breakdown = dict(ranking.copr_breakdown or {})
                breakdown[category] = numeric_value
                ranking.copr_breakdown = breakdown

                mapped_field = self.CATEGORY_TO_FIELD.get(category)
                if mapped_field:
                    setattr(ranking, mapped_field, numeric_value)

                ranking.save()

 #               self.stdout.write(
 #                   self.style.SUCCESS(
 #                       f"Updated COPR stats for team {team_number} - {category}: {round(value, 2)}"
 #                   )
 #              )

        self.stdout.write(self.style.SUCCESS("Team rank + COPR stats update completed"))
