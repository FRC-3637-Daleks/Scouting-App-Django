from django.core.management.base import BaseCommand
import requests
from cachecontrol import CacheControl
from scouting.models import *
from django.core.exceptions import ObjectDoesNotExist

class Command(BaseCommand):
    help = 'Update team COPRs (Component OPRs) for L1-L4 coral count from The Blue Alliance API'

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
        url = f'https://www.thebluealliance.com/api/v3/event/{event.tba_event_key}/coprs'
        response = session.get(url, headers=headers)
        if response.status_code != 200:
            self.stdout.write(self.style.ERROR(f"Failed to fetch data from TBA: {response.status_code}"))
            return

        coprs_data = response.json()
        if not coprs_data:
            self.stdout.write(self.style.ERROR("No COPR data available"))
            return

        # The JSON response contains four keys: "L1 Coral Count", "L2 Coral Count", etc.
        categories = ["L1 Coral Count", "L2 Coral Count", "L3 Coral Count", "L4 Coral Count", "netAlgaeCount", "wallAlgaeCount", "autoCoralCount", "foulCount"]

        # Process each category
        for category in categories:
            coral_dict = coprs_data.get(category, {})
            # Loop over each team in this category
            for team_key, value in coral_dict.items():
                if not team_key.startswith("frc"):
                    continue  # Skip non-team keys

                team_number = team_key[3:]  # Remove the "frc" prefix
                try:
                    team = Team.objects.get(team_number=team_number)
                except Team.DoesNotExist:
                    self.stdout.write(self.style.WARNING(f"Team {team_number} not found in database"))
                    continue

                # Update or create the TeamRanking record
                ranking, created = TeamRanking.objects.get_or_create(
                    team=team,
                    event=event,
                    defaults={'rank': 0}
                )

                # Assign the appropriate coral count value based on the category
                if category == "L1 Coral Count":
                    ranking.l1_coral = round(value, 2)
                elif category == "L2 Coral Count":
                    ranking.l2_coral = round(value, 2)
                elif category == "L3 Coral Count":
                    ranking.l3_coral = round(value, 2)
                elif category == "L4 Coral Count":
                    ranking.l4_coral = round(value, 2)
                elif category == "netAlgaeCount":
                    ranking.net_algae_count = round(value, 2)
                elif category == "wallAlgaeCount":
                    ranking.wall_algae_count = round(value, 2)
                elif category == "autoCoralCount":
                    ranking.auto_coral_count = round(value, 2)
                elif category == "foulCount":
                    ranking.foul_count = round(value, 2)

                ranking.save()

                self.stdout.write(
                    self.style.SUCCESS(
                        f"Updated COPR stats for team {team_number} - {category}: {round(value, 2)}"
                    )
                )

        self.stdout.write(self.style.SUCCESS("Team COPR stats update completed"))
