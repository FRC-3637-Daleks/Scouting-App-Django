from django.core.management.base import BaseCommand
import tbapy
from scouting.models import *
from django.core.exceptions import ObjectDoesNotExist


class Command(BaseCommand):
    help = 'Update team rank, OPR, DPR, and CCWM stats from The Blue Alliance API'

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
            rankings_list = rankings_response.get('rankings', []) if isinstance(rankings_response, dict) else []
            sort_order_info = rankings_response.get('sort_order_info', []) if isinstance(rankings_response, dict) else []
            rp_index = None
            for index, order_info in enumerate(sort_order_info):
                name = str((order_info or {}).get("name") or "").lower()
                if "ranking point" in name or name == "rp":
                    rp_index = index
                    break
            # TBA often exposes this as "Ranking Score" in sort order index 0.
            if rp_index is None and sort_order_info:
                rp_index = 0
            for rank_data in rankings_list:
                team_key = rank_data.get('team_key')
                if not team_key or not str(team_key).startswith('frc'):
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
                ranking.rank = rank_data.get('rank', ranking.rank or 0)
                ranking_points = None
                sort_orders = rank_data.get("sort_orders") or []
                if rp_index is not None and len(sort_orders) > rp_index:
                    try:
                        ranking_points = round(float(sort_orders[rp_index]), 2)
                    except (TypeError, ValueError):
                        ranking_points = None
                ranking.ranking_points = ranking_points
                ranking.save(update_fields=['rank', 'ranking_points'])

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

            self.stdout.write(self.style.SUCCESS("Team rank + OPR stats update completed"))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Unexpected error: {str(e)}"))
