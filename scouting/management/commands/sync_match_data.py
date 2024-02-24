from django.core.management.base import BaseCommand
from django.core import serializers
import requests
from scouting.models import *
from django.conf import settings


class Command(BaseCommand):
    help = 'Sync MatchData2024 objects to Server B'

    def handle(self, *args, **options):
        # Fetch the MatchData2024 objects that need to be synced
        event = Event.objects.get(active=True)
        data = MatchData2024.objects.all()

        # Serialize the data into JSON
        serialized_data = serializers.serialize('json', data)

        # Send a POST request to Server B with the serialized data
        master_server_url = 'http://' + settings.SYNC_MASTER_SERVER + '/sync/matchdata'
        response = requests.post('http://localhost:8001/sync/matchdata', data=serialized_data, auth=(settings.SYNC_ACCOUNT_USERNAME, settings.SYNC_ACCOUNT_PASSWORD))

        if response.status_code == 200:
            self.stdout.write(self.style.SUCCESS('Successfully synced data to Server B'))
        else:
            self.stdout.write(self.style.ERROR('Failed to sync data to Server B'))
