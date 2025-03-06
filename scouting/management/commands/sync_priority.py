from django.core.management.base import BaseCommand
from scouting.models import Team, Event, TeamRanking


class Command(BaseCommand):
    help = 'Updates the priority for a team'

    def add_arguments(self, parser):
        parser.add_argument('team_number', type=str)
        parser.add_argument('priority', type=str)  # Changed to str to handle POST data

    def handle(self, *args, **options):
        team_number = options['team_number']
        try:
            priority = int(options['priority'])  # Convert to int here
            if not (1 <= priority <= 5):
                raise ValueError("Priority must be between 1 and 5")

            event = Event.objects.get(active=True)
            team = Team.objects.get(team_number=team_number)
            team_ranking, created = TeamRanking.objects.get_or_create(
                team=team,
                event=event,
                defaults={'rank': 0, 'ranking_score': 0, 'matches_played': 0}
            )
            team_ranking.priority = priority
            team_ranking.save()
            self.stdout.write(self.style.SUCCESS(f'Successfully updated priority for team {team_number}'))
        except ValueError as e:
            self.stdout.write(self.style.ERROR(f'Error: {str(e)}'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error: {str(e)}'))
