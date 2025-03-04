# scouting/consumers.py
import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from .models import Team, Event, TeamRanking

class PriorityConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.group_name = "priority_updates"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data):
        data = json.loads(text_data)
        team_number = data.get('team_number')
        priority_value = data.get('priority')
        if team_number and priority_value:
            # Update the database (wrapped in database_sync_to_async)
            success = await self.update_priority(team_number, priority_value)
            if success:
                # Broadcast the updated priority to the group
                await self.channel_layer.group_send(
                    self.group_name,
                    {
                        'type': 'priority_update',
                        'team_number': team_number,
                        'priority': priority_value,
                    }
                )

    async def priority_update(self, event):
        # Send the update to the WebSocket
        await self.send(text_data=json.dumps({
            'team_number': event['team_number'],
            'priority': event['priority'],
        }))

    @database_sync_to_async
    def update_priority(self, team_number, priority_value):
        try:
            priority_value = int(priority_value)
            if priority_value < 1 or priority_value > 5:
                return False
            team = Team.objects.get(team_number=team_number)
            event = Event.objects.get(active=True)
            team_ranking, _ = TeamRanking.objects.get_or_create(team=team, event=event)
            team_ranking.priority = priority_value
            team_ranking.save()
            return True
        except Exception as e:
            print("Error updating priority:", e)
            return False
