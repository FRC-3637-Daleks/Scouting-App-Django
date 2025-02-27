from django.core.management.base import BaseCommand
import tbapy
from scouting.models import *
from django.core.exceptions import ObjectDoesNotExist


class Command(BaseCommand):
    help = 'Update team OPR, DPR, and CCWM stats from The Blue Alliance API'

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
            oprs_response = tba.event_oprs(event.tba_event_key)

            if not oprs_response:
                self.stdout.write(self.style.ERROR("No OPR data available"))
                return

            oprs = oprs_response.get('oprs', {})
            dprs = oprs_response.get('dprs', {})
            ccwms = oprs_response.get('ccwms', {})

            for team_key in oprs:
                try:
                    team_number = team_key[3:]  # Remove "frc" prefix
                    try:
                        team = Team.objects.get(team_number=team_number)

                        # Update or create TeamRanking
                        ranking, created = TeamRanking.objects.get_or_create(
                            team=team,
                            event=event,
                            defaults={'rank': 0}
                        )

                        # Update OPR stats
                        ranking.opr = round(oprs.get(team_key, 0), 2)
                        ranking.dpr = round(dprs.get(team_key, 0), 2)
                        ranking.ccwm = round(ccwms.get(team_key, 0), 2)
                        ranking.save()

                        self.stdout.write(
                            self.style.SUCCESS(
                                f"Updated OPR stats for team {team_number}"
                            )
                        )

                    except Team.DoesNotExist:
                        self.stdout.write(
                            self.style.WARNING(f"Team {team_number} not found in database")
                        )
                        continue

                except Exception as e:
                    self.stdout.write(
                        self.style.WARNING(f"Error processing team {team_key}: {str(e)}")
                    )
                    continue

            self.stdout.write(self.style.SUCCESS("Team OPR stats update completed"))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Unexpected error: {str(e)}"))
