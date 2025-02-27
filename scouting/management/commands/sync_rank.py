from django.core.management.base import BaseCommand
import tbapy
from scouting.models import *
from django.core.exceptions import ObjectDoesNotExist


class Command(BaseCommand):
    help = 'Update team rankings from The Blue Alliance API'

    def handle(self, *args, **options):
        try:
            api_key = TbaApiKey.objects.get(active=True).api_key
        except ObjectDoesNotExist:
            self.stdout.write(self.style.ERROR("Active API key not found."))
            return

        tba = tbapy.TBA(api_key)

        try:
            event = Event.objects.get(active=True)
        except Event.DoesNotExist:
            self.stdout.write(self.style.ERROR("No active event found."))
            return

        try:
            rankings_response = tba.event_rankings(event.tba_event_key)

            if 'rankings' not in rankings_response:
                self.stdout.write(self.style.ERROR("No rankings data available"))
                return

            # Store sort order info for later use
            sort_order_info = rankings_response.get('sort_order_info', [])

            for rank_data in rankings_response['rankings']:
                try:
                    team_number = rank_data['team_key'][3:]  # Remove "frc" prefix

                    try:
                        team = Team.objects.get(team_number=team_number)

                        # Create extra stats dictionary


                        # Handle extra_stats


                        # Handle sort_orders


                        # Handle record


                        # Update or create ranking
                        ranking, created = TeamRanking.objects.update_or_create(
                            team=team,
                            event=event,
                            defaults={
                                'rank': rank_data.get('rank', 0),
                                'matches_played': rank_data.get('matches_played', 0),
                                'ranking_score': (
                                    rank_data['sort_orders'][0]
                                    if rank_data.get('sort_orders')
                                    else 0
                                ),

                            }
                        )

                        self.stdout.write(
                            self.style.SUCCESS(
                                f"{'Created' if created else 'Updated'} ranking for team {team_number}"
                            )
                        )

                    except Team.DoesNotExist:
                        self.stdout.write(self.style.WARNING(f"Team {team_number} not found in database"))
                        continue

                except KeyError as e:
                    self.stdout.write(self.style.WARNING(f"Error processing rank data: Missing key {str(e)}"))
                    continue

            self.stdout.write(self.style.SUCCESS("Team rankings update completed"))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Unexpected error: {str(e)}"))
