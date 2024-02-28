from django.core.management.base import BaseCommand
from django.core import serializers
import requests
from scouting.models import *
from django.conf import settings
from rest_framework.authtoken.models import Token  # Import Token model
from django.contrib.auth.models import User  # Import User model
from django.core.management.base import BaseCommand

class Command(BaseCommand):
    help = 'Sync MatchData2024 objects to Server B'

    def handle(self, *args, **options):
        # Fetch the MatchData2024 objects that need to be synced
        event = Event.objects.get(active=True)
        data = MatchData2024.objects.all()

        # Serialize the data into JSON
        serialized_data = serializers.serialize('json', data)

        try:
            # Retrieve the user with username 'sync'
            user_sync = User.objects.get(username='sync')

            # Get or create the token associated with the user
            # token, created = Token.objects.get(user=user_sync)
            token='f1bdeb03d261b9d2eaa6f6bc9e40c5f7e259cb49'

            # Send a POST request to Server B with the serialized data and token
            master_server_url = settings.SYNC_MASTER_SERVER + '/sync/matchdata'
            # headers = {'Authorization': f'Token {token.key}'}
            headers = {'Authorization': f'Token {token}'}
            response = requests.post(master_server_url, data=serialized_data, headers=headers)

            if response.status_code == 200:
                self.stdout.write(self.style.SUCCESS('Successfully synced data to Server B'))
            else:
                self.stdout.write(self.style.ERROR('Failed to sync data to Server B'))
        except User.DoesNotExist:
            self.stdout.write(self.style.ERROR("User 'sync' does not exist"))
